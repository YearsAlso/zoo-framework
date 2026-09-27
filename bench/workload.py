"""代表性业务负载（adopt-rust-core 任务 1.4 的产物）.

**这是替身，不是真实业务 trace。** 仓库中没有任何真实负载样本，本模块用一个
"形状接近真实业务"的 Worker 执行体来近似：结构化数据编解码 + 字符串处理 +
一次短 I/O 等待。选择这三类是因为它们覆盖了 Python Worker 最常见的三种成本来源：

- 编解码：CPU 密集且纯 Python（Rust 化收益的理论上限所在）
- 字符串处理：同上
- 短 I/O：GIL 会释放，是异步/并发收益最明显的部分

**结论的适用边界**：本模块测出的"框架开销占比"只对该形状的负载成立。真实负载若
以长时 I/O 为主（占比会更高）或以纯计算为主（占比会更低），需要以真实 trace 重测。
这一点已在 design 的 Risks 中标注。
"""

import json
import time

#: 代表性负载里一次"短 I/O"的时长。真实业务的 I/O 分布未知，此处固定为一个
#: 便于对照的小值；占比结论对该值敏感，报告中必须一并给出。
DEFAULT_IO_WAIT = 0.0


def representative_body(io_wait: float = DEFAULT_IO_WAIT, scale: int = 1) -> int:
    """代表性 Worker 执行体.

    Args:
        io_wait: 模拟 I/O 的等待时长（秒）
        scale: 重复次数，用于把执行体拉到不同的耗时档位。用重复而非 sleep 拉长，
            是为了让 CPU 档位的耗时可控且不受平台定时器精度影响

    Returns:
        编码后的载荷长度（避免整个函数被优化掉）
    """
    total = 0
    parts_count = 0

    for _ in range(scale):
        payload = {
            "id": 42,
            "items": [{"k": n, "v": n * 1.5, "tag": f"tag-{n:03d}"} for n in range(20)],
            "ts": time.time(),
        }
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)

        text = " ".join(item["tag"] for item in decoded["items"])
        total += len(encoded)
        parts_count += len(text.split("-"))

    if io_wait:
        time.sleep(io_wait)

    return total + parts_count


def measure_body_duration(repeats: int = 200, io_wait: float = DEFAULT_IO_WAIT) -> float:
    """测量代表性执行体的单次耗时（秒）.

    **仅用于挑选档位与记录参照值。** 占比计算 MUST NOT 用它做减法——
    单独测量的耗时与端到端运行中的耗时不在同一状态下，相减会引入系统性偏差。
    端到端内的执行体耗时由探针 Worker 自行埋点（见 profile_framework.py）。

    Returns:
        中位耗时
    """
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        representative_body(io_wait)
        samples.append(time.perf_counter() - start)
    samples.sort()
    return samples[len(samples) // 2]
