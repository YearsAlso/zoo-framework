## ADDED Requirements

### Requirement: 背压容量准入 MUST 同时约束启动期与运行期注册

调度器 MUST 对进入调度列表的每一个 Worker 应用同一套背压容量准入，启动期 muster 与运行期注册
MUST NOT 走两套不同规则。运行期新增使 Worker 数超过池容量时：`reject` 策略 MUST 明确拒绝并抛出
错误，且该 Worker MUST NOT 进入调度列表；`queue` 策略 MUST 照常接纳（超出的排队）；`expand` 策略
放宽后的生效容量 MUST 对**已在运行**的容器同样生效，MUST NOT 只更新一个不起作用的值。无容量概念
的线程模型 MUST 始终接纳。准入 MUST NOT 使停机后的调度器复活：停机后运行期注册 MUST NOT 重建容器
或产生新的派发。

#### Scenario: reject 策略拒绝运行期超容量注册
- **WHEN** 池尺寸 2、策略为 reject 的调度器已调度 2 个 Worker，随后运行期新增第 3 个
- **THEN** 该新增被拒绝并抛出错误，且该 Worker MUST NOT 出现在调度列表中

#### Scenario: queue 策略照常接纳运行期新增
- **WHEN** 池尺寸 2、策略为 queue 的调度器运行期新增超过容量的 Worker
- **THEN** 新增被接纳进入调度并按排队语义执行，生效池尺寸保持不变

#### Scenario: expand 策略在运行期真实放宽容器
- **WHEN** 池尺寸 1、策略为 expand 的调度器已运行，随后运行期新增 Worker 使所需容量超过当前生效
  尺寸
- **THEN** 生效容量被放宽，且运行中的池实际增补到该容量

#### Scenario: 线程模型无条件接纳运行期注册
- **WHEN** 线程（无池）模型下运行期新增 Worker
- **THEN** 新增被接纳进入调度，不受容量限制

#### Scenario: 停机后运行期注册不复活调度
- **WHEN** 调度器已停机，随后调用运行期注册
- **THEN** 准入不重建容器、不产生新的派发
