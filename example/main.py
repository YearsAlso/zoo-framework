# 副作用导入：`threads/demo_thread.py` 里的 `@worker(count=20)` 在**导入时**才注册
# 那个示例 Worker，因此这行不是"没用到的导入"。（注：它注册进的是旧的 `WorkerRegister`，
# 而 `Master` 从 `WorkerRegistry` 调度，故这个示例 Worker 目前实际不会被调度——见
# 本变更任务表 7.1 的记录。保留导入是为了不把原有行为一并删掉。）
import threads  # noqa: F401

from zoo_framework.core import Master


def main() -> None:
    # Master 现在的签名是 Master(config: MasterConfig | None = None)；
    # 原先这里传整数 1，会在 __init__ 里被当成配置对象使用而抛 AttributeError。
    master = Master()
    master.run()


if __name__ == "__main__":
    main()
