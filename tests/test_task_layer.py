"""add-task-layer：任务值对象 + 落到状态机持久化作用域的可持久化任务队列。

覆盖 spec delta（``openspec/changes/add-task-layer/specs/task-queue/spec.md``）的 ADDED
场景：身份与 Worker 解耦、生命周期迁移、重启不丢排队中的活、重启后执行中任务不被静默重跑、
并发迁移原子、重复身份显式拒绝、取消诚实性，以及未使用任务层时的零行为变化。
"""

import pickle
import threading

import pytest

from zoo_framework.statemachine import StateMachineManager
from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.tasks import Task, TaskQueue, TaskStatus

SCOPE = "zoo.tasks.test"


def _queue(manager: StateMachineManager | None = None) -> TaskQueue:
    """构造一个注入管理器（便于在同一进程内模拟重启）的测试队列。"""
    return TaskQueue(SCOPE, manager=manager)


def _restart(sm: StateMachineManager) -> None:
    """模拟一次进程重启：pickle 往返后经既有恢复入口载入（整表替换）。"""
    sm.load_state_machines(pickle.loads(pickle.dumps(sm.get_state_machines())))


def _install_read_gate(monkeypatch, parties: int) -> None:
    """在 ``StateNode.get_value`` 上装一个「读闸门」，让「读取-改-写」的竞态**确定性地**
    暴露，不依赖 GIL 切换时机。

    默认切换间隔下临界区只有几微秒，一个丢失更新的实现也能侥幸通过并发用例。闸门在
    每个参与者**第一次**读值时：**先取值**（保证所有参与者都拿到同一份旧快照），再于
    屏障处会合（保证在任一参与者写入前，其余都已读到该快照）。于是正确的 CAS 实现会
    在版本冲突时重试并收敛，丢失更新的实现则互相覆盖。取值在等待之前完成是关键——只
    同步到达时刻并不足以让两个线程都先读到旧值。每个线程只等一次（线程局部标记），
    重试不会二次等待，故不会死锁；参与者迟迟不到会以 ``BrokenBarrierError`` 显式失败。

    Args:
        monkeypatch: pytest 的 monkeypatch fixture
        parties: 参与者线程数（每个线程须至少调用一次 ``get_value``）
    """
    barrier = threading.Barrier(parties)
    local = threading.local()
    # 安装者（通常是主线程，负责 setup 与 join 后的断言）永不等待——它不参与竞态，
    # 若也去等会因人数不足而超时。工作线程各自持有全新的线程局部，才会进入闸门。
    local.waited = True
    real = StateNode.get_value

    def gated(self):
        value = real(self)
        if not getattr(local, "waited", False):
            local.waited = True
            barrier.wait(timeout=5)
        return value

    monkeypatch.setattr(StateNode, "get_value", gated)


class TestTaskValueObject:
    """形状 1：任务值对象——身份 / 载荷 / 状态 / 尝试 / 结果 / 错误 / 时间戳。"""

    def test_task_carries_identity_payload_and_timestamps(self):
        """Scenario: 任务携带身份、载荷与时间戳."""
        task = Task.new({"n": 1}, task_id="T-1")

        assert task.task_id == "T-1"
        assert task.payload == {"n": 1}
        assert task.created_at > 0
        assert task.updated_at > 0

    def test_new_generates_distinct_identities(self):
        """``Task.new`` 在未给身份时自动生成唯一身份."""
        first, second = Task.new(), Task.new()

        assert first.task_id and second.task_id
        assert first.task_id != second.task_id
        assert first.status is TaskStatus.PENDING
        assert first.attempts == 0

    def test_identity_is_not_bound_to_any_worker(self):
        """Scenario: 任务身份不绑定任何 Worker（同一队列可承载任意身份的任务）."""
        sm = StateMachineManager()
        queue = _queue(sm)

        queue.submit(Task.new(payload="a", task_id="worker-agnostic-1"))
        queue.submit(Task.new(payload="b", task_id="worker-agnostic-2"))

        assert queue.get("worker-agnostic-1").task_id == "worker-agnostic-1"
        assert queue.get("worker-agnostic-2").task_id == "worker-agnostic-2"

    def test_empty_identity_is_rejected(self):
        """Scenario: 缺少身份的任务被显式拒绝."""
        sm = StateMachineManager()
        queue = _queue(sm)

        with pytest.raises(ValueError):
            queue.submit(Task(payload="x", task_id=""))

        assert queue.tasks() == []

    def test_dict_roundtrip_is_lossless(self):
        """``to_dict`` / ``from_dict`` 往返一致."""
        task = Task.new({"k": [1, 2]}, task_id="T-2")
        task.status = TaskStatus.RUNNING
        task.attempts = 3
        task.started_at = 123.0

        restored = Task.from_dict(task.to_dict())

        assert restored.task_id == task.task_id
        assert restored.payload == task.payload
        assert restored.status == TaskStatus.RUNNING
        assert restored.attempts == 3
        assert restored.started_at == 123.0

    def test_unknown_status_literal_raises(self):
        """未知状态字面量显式失败（不静默退化）."""
        with pytest.raises(ValueError):
            Task.from_dict(
                {
                    "task_id": "T-3",
                    "status": "not-a-status",
                    "created_at": 1.0,
                    "updated_at": 1.0,
                }
            )

    def test_string_status_is_coerced(self):
        """以字符串构造时状态自动归一为 ``TaskStatus``."""
        assert Task(task_id="T-4", status="pending").status is TaskStatus.PENDING


class TestLifecycle:
    """形状 1 的生命周期迁移契约。"""

    def test_new_task_starts_pending(self):
        """Scenario: 新任务初始为待跑."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))

        task = queue.get("A")
        assert task.status is TaskStatus.PENDING
        assert task.attempts == 0

    def test_claim_moves_to_running_and_bumps_attempts(self):
        """Scenario: 认领后进入执行中且尝试次数递增."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))

        claimed = queue.claim("A")

        assert claimed.status is TaskStatus.RUNNING
        assert claimed.attempts == 1
        assert claimed.started_at is not None

    def test_complete_records_result(self):
        """Scenario: 完成后记录结果."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))
        queue.claim("A")

        done = queue.complete("A", result={"ok": True})

        assert done.status is TaskStatus.SUCCEEDED
        assert done.result == {"ok": True}
        assert done.finished_at is not None

    def test_fail_records_error(self):
        """Scenario: 失败后记录错误."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))
        queue.claim("A")

        failed = queue.fail("A", error=RuntimeError("boom"))

        assert failed.status is TaskStatus.FAILED
        assert "boom" in failed.error

    def test_illegal_transition_is_rejected(self):
        """Scenario: 非法迁移被显式拒绝（对已完成任务再次认领）."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))
        queue.claim("A")
        queue.complete("A")

        assert queue.claim("A") is None
        assert queue.get("A").status is TaskStatus.SUCCEEDED

    def test_complete_and_fail_require_running(self):
        """完成 / 失败只对执行中任务生效."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))

        assert queue.complete("A") is None
        assert queue.fail("A", "x") is None
        assert queue.get("A").status is TaskStatus.PENDING

    def test_claim_next_takes_oldest_pending(self):
        """``claim_next`` 认领最老的待跑任务."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))
        queue.submit(Task.new({}, task_id="B"))
        queue.cancel("A")

        claimed = queue.claim_next()

        assert claimed.task_id == "B"
        assert queue.claim_next() is None


class TestDurableQueue:
    """形状 2：持久化与重启恢复。"""

    def test_submit_then_query_by_identity_and_status(self):
        """Scenario: 提交后可按身份与状态查询."""
        sm = StateMachineManager()
        queue = _queue(sm)
        queue.submit(Task.new({"n": 1}, task_id="A"))
        queue.submit(Task.new({"n": 2}, task_id="B"))

        assert queue.get("A").payload == {"n": 1}
        assert {t.task_id for t in queue.tasks(TaskStatus.PENDING)} == {"A", "B"}

    def test_pending_survives_restart(self):
        """Scenario: 重启后排队中的任务不丢（身份 / 载荷 / 状态 / 尝试次数一致）."""
        sm = StateMachineManager()
        queue = _queue(sm)
        queue.submit(Task.new({"n": 1}, task_id="A"))
        queue.submit(Task.new({"n": 2}, task_id="B"))

        _restart(sm)
        restored = _queue(sm)

        assert restored.get("A").payload == {"n": 1}
        assert restored.get("A").status is TaskStatus.PENDING
        assert restored.get("A").attempts == 0
        assert restored.get("B").payload == {"n": 2}

    def test_submission_order_survives_restart(self):
        """Scenario: 提交顺序在重启后保持."""
        sm = StateMachineManager()
        queue = _queue(sm)
        for name in ("A", "B", "C"):
            queue.submit(Task.new({}, task_id=name))

        _restart(sm)

        assert [t.task_id for t in _queue(sm).tasks()] == ["A", "B", "C"]

    def test_query_missing_task_returns_none(self):
        """Scenario: 查询不存在的任务返回空."""
        assert _queue().get("never-submitted") is None

    def test_queue_node_is_visible_to_state_machine(self):
        """队列数据落在状态机作用域内（持久化的前提）."""
        sm = StateMachineManager()
        queue = _queue(sm)
        queue.submit(Task.new({}, task_id="A"))

        raw = sm.get_state(SCOPE, "tasks")
        assert isinstance(raw, list)
        assert raw[0]["task_id"] == "A"


class TestRestartRecovery:
    """重启后处于执行中的任务不得被静默重跑。"""

    def test_running_task_stays_running_and_is_not_rerun(self):
        """Scenario: 重启后原执行中任务保持可查询且不被自动重跑."""
        sm = StateMachineManager()
        queue = _queue(sm)
        queue.submit(Task.new({}, task_id="A"))
        queue.claim("A")

        _restart(sm)
        restored = _queue(sm)

        assert restored.get("A").status is TaskStatus.RUNNING
        assert restored.claim_next() is None  # 没有待跑任务，不会被静默改回待跑并重跑

    def test_explicit_requeue_returns_to_pending(self):
        """Scenario: 显式重新排队把执行中任务改回待跑（尝试次数不再额外递增）."""
        sm = StateMachineManager()
        queue = _queue(sm)
        queue.submit(Task.new({}, task_id="A"))
        queue.claim("A")

        _restart(sm)
        restored = _queue(sm)
        requeued = restored.requeue("A")

        assert requeued.status is TaskStatus.PENDING
        assert requeued.attempts == 1  # 认领时已 +1，重新排队不再递增
        assert restored.claim("A").attempts == 2


class TestAtomicity:
    """并发迁移的原子性。"""

    def test_concurrent_claim_only_one_wins(self, monkeypatch):
        """Scenario: 并发认领同一任务恰好一个成功."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))
        _install_read_gate(monkeypatch, parties=2)
        barrier = threading.Barrier(2)
        outcomes: list[Task | None] = []

        def worker() -> None:
            barrier.wait()
            outcomes.append(queue.claim("A"))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert [o is None for o in outcomes].count(True) == 1
        assert [o is None for o in outcomes].count(False) == 1
        assert queue.get("A").status is TaskStatus.RUNNING
        assert queue.get("A").attempts == 1

    def test_concurrent_submit_does_not_lose_updates(self, monkeypatch):
        """Scenario: 并发提交不同任务不丢更新."""
        queue = _queue()
        per_thread = 5
        thread_count = 6
        _install_read_gate(monkeypatch, parties=thread_count)
        barrier = threading.Barrier(thread_count)

        def worker(index: int) -> None:
            barrier.wait()
            for n in range(per_thread):
                queue.submit(Task.new({"i": index, "n": n}, task_id=f"{index}-{n}"))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = thread_count * per_thread
        assert len(queue.tasks()) == expected

    def test_concurrent_submit_and_claim_stay_consistent(self, monkeypatch):
        """并发提交与认领混跑下任务数自洽、无丢更新."""
        queue = _queue()
        submitters = 4
        per_submitter = 5
        _install_read_gate(monkeypatch, parties=submitters + 1)
        barrier = threading.Barrier(submitters + 1)
        claimed: list[Task | None] = []
        claimed_lock = threading.Lock()

        def submitter(index: int) -> None:
            barrier.wait()
            for n in range(per_submitter):
                queue.submit(Task.new({}, task_id=f"{index}-{n}"))

        def claimer() -> None:
            barrier.wait()
            for _ in range(per_submitter * submitters):
                task = queue.claim_next()
                with claimed_lock:
                    claimed.append(task)

        threads = [threading.Thread(target=submitter, args=(i,)) for i in range(submitters)]
        threads.append(threading.Thread(target=claimer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total = submitters * per_submitter
        assert len(queue.tasks()) == total
        assert sum(1 for c in claimed if c is not None) == sum(t.attempts for t in queue.tasks())


class TestDuplicateIdentity:
    """身份唯一性拒绝，且不含投递幂等承诺。"""

    def test_duplicate_submit_is_rejected_and_queue_unchanged(self):
        """Scenario: 重复提交同一身份被显式拒绝且队列不变."""
        queue = _queue()
        queue.submit(Task.new({"n": 1}, task_id="X"))

        with pytest.raises(ValueError):
            queue.submit(Task.new({"n": 2}, task_id="X"))

        assert len(queue.tasks()) == 1
        assert queue.get("X").payload == {"n": 1}

    def test_rejection_makes_no_delivery_idempotency_claim(self):
        """Scenario: 拒绝不含投递幂等承诺（终态任务的身份仍占用，重提交仍被拒）."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="X"))
        queue.claim("X")
        queue.complete("X", result=1)

        with pytest.raises(ValueError):
            queue.submit(Task.new({}, task_id="X"))

        # 队列不因"已存在"而对该次提交做任何去重 / 恰好一次保证，只是身份被占用。
        assert len(queue.tasks()) == 1


class TestCancellation:
    """取消只阻止尚未启动的任务（诚实边界）。"""

    def test_cancel_pending_prevents_claim(self):
        """Scenario: 取消待跑任务后不再可认领."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))

        assert queue.cancel("A") is True
        assert queue.get("A").status is TaskStatus.CANCELLED
        assert queue.claim("A") is None

    def test_cancel_running_has_no_effect(self):
        """Scenario: 取消执行中的任务不生效（也不声称中断已开始的执行）."""
        queue = _queue()
        queue.submit(Task.new({}, task_id="A"))
        queue.claim("A")

        assert queue.cancel("A") is False
        assert queue.get("A").status is TaskStatus.RUNNING

    def test_cancel_missing_task_returns_false(self):
        """取消不存在的任务返回 False（不抛错）."""
        assert _queue().cancel("nope") is False


class TestZeroBehaviorChange:
    """未使用任务层时既有行为不变；唯一新键默认保持现状。"""

    def test_constructing_queue_creates_no_scope(self):
        """Scenario: 不使用任务层时既有行为不变（构造 / 读取不产生副作用）."""
        sm = StateMachineManager()

        queue = _queue(sm)
        assert queue.tasks() == []

        assert not sm.get_state_machines().has_key(SCOPE)

    def test_unrelated_state_work_is_unaffected(self):
        """既有状态写入不受任务层影响（不产生任务作用域）."""
        sm = StateMachineManager()
        sm.set_state("other", "k", "v")

        assert sm.get_state("other", "k") == "v"
        assert not sm.get_state_machines().has_key(SCOPE)

    def test_default_scope_keeps_current_behavior(self):
        """Scenario: 未配置新键时取默认作用域名，且默认值保持现状."""
        from zoo_framework.params import TaskParams

        assert TaskParams.QUEUE_SCOPE == "zoo.tasks"
        assert TaskQueue()._scope_name == "zoo.tasks"

    def test_scope_read_from_config_at_runtime(self, monkeypatch):
        """配置键在运行期读取（打桩后新建队列即生效）."""
        from zoo_framework.params import TaskParams

        monkeypatch.setattr(TaskParams, "QUEUE_SCOPE", "custom.scope")

        assert TaskQueue()._scope_name == "custom.scope"
