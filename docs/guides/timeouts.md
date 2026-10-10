# 超时与熔断

## 最重要的一句话

**框架不会强制终止正在执行的 Worker。** `run_timeout` 的行为是**观察并停止派发**：
超过时限后，这个 Worker 不再被排进调度，但**已经在跑的那一次会继续跑完**。

这是刻意的设计，不是缺陷。Python 里没有安全的线程强杀机制——`PyThreadState_SetAsyncExc`
之类的做法会留下锁未释放、状态不一致的进程。假装能强杀会制造更难排查的问题。

## 怎么用

全局：

```json
{ "worker": { "runTimeout": 30 } }
```

单个 Worker（在构造时声明）：

```python
super().__init__({
    "is_loop": True,
    "delay_time": 5,
    "name": "OrderSync",
    "run_timeout": 30,
})
```

## 触发后会发生什么

```
1. 某次 _execute() 超过 run_timeout
2. 框架在下一轮调度时观察到这一点
3. 该 Worker 被"熔断"——不再被派发
4. 正在执行的那一次继续跑到自然结束
5. 已在飞的那次结束时会走正常的结算路径
```

**注意第 4 步**：如果那次执行本身永不返回（例如卡在一个没有超时的网络请求上），
它就是永不返回。框架不会救你——但也不会假装救了。

## 因此你需要自己响应取消

既然不会被强杀，**超时之后要不要停，必须由你的代码决定**。
常见做法是在 `_execute()` 内部使用自己的超时机制：

```python
import socket

class FetchWorker(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "Fetch"})

    def _execute(self):
        # 自己控制单次执行的时间上界
        with socket.setdefaulttimeout(10):
            do_network_call()
```

`run_timeout` 是**调度层的保险丝**（防止一个卡住的任务反复占用调度轮次），
不是**执行层的取消机制**。

## 与背压策略的关系

| 机制 | 层次 | 作用 |
|---|---|---|
| `worker:runTimeout` | 调度层 | 卡住就停止派发 |
| `worker:runPolicy` | 池层 | 池满时扩容 / 排队 / 拒绝 |
| 你自己的超时 | 执行层 | 真正让一次执行提前结束 |

三者互补，不能互相替代。

## 在飞去重

同一轮调度里，一个**仍在执行中**的 Worker 会被跳过，**不会并发派发两次**。
这条保证是内建的，不需要你写锁。

## 相关

- [配置参考](config-reference.md)
- [状态持久化](state-persistence.md) —— 熔断后状态会怎样
