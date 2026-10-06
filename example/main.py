# Worker 的接通注册路径：Master.register_worker（变更 cleanup-aop-public-surface 前
# 这里是副作用导入 + `@worker(count=20)`，写入的是不被 Master 读取的 legacy 表，
# 示例 Worker 实际从不被调度——见 issue #49）。
from threads import DemoThread

from zoo_framework.core import Master


def main() -> None:
    # Master 现在的签名是 Master(config: MasterConfig | None = None)；
    # 原先这里传整数 1，会在 __init__ 里被当成配置对象使用而抛 AttributeError。
    master = Master()
    master.register_worker("TestThread", DemoThread)
    master.run()


if __name__ == "__main__":
    main()
