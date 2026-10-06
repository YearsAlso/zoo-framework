## Purpose（本变更新增条款）

线程安全字典的互斥归属：锁按实例持有、取进程内线程锁，消除"模块级单把 multiprocessing 锁串行化全进程"的形态。

## ADDED Requirements

### Requirement: ThreadSafeDict MUST 每实例持锁且使用进程内线程锁

`ThreadSafeDict` 的互斥锁 SHALL 按**实例**持有：不同实例之间的读写 MUST NOT 因共享同一把锁而互相串行。锁的实现 MUST 为进程内线程锁（`threading` 级），MUST NOT 使用 `multiprocessing.Lock`——单进程场景下它既语义不符又有一个数量级的额外代价。每个实例的锁归属 MUST 可显式声明：实例被整体替换时，其锁随之更替，不残留进程级共享。

#### Scenario: 两个实例互不阻塞
- **WHEN** 一个实例正在锁内执行慢操作，同时对另一个实例进行常规读写
- **THEN** 另一实例的读写不被该慢操作阻塞，立即完成

#### Scenario: 同一实例并发读写不丢更新
- **WHEN** 多个线程并发对同一实例执行写入与读取
- **THEN** 不出现丢失的写入，任一读取观察到的是完整写入后的状态

#### Scenario: 锁为 threading 级且按实例持有
- **WHEN** 检查两个 `ThreadSafeDict` 实例各自持有的锁
- **THEN** 两者是 `threading.RLock` 且为不同的锁对象
