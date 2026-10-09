# Proposal: add-adaptive-scheduling

> **状态：已重开（bandit 方案）—— 维护者 2026-10-09 指示「用 bandit 替代 ML，ML 不再推进」。**
> 历史脉络见文末「延后记录」，其中导出机制结论已明确**不适用于** bandit 方案。

## Why

当前框架的调度决策是**静态的**：worker 走哪个池、native 开不开，全部在启动时由 config.json 冻结。阶段 0 实测（`native/DECISION.md`）证明了两件事：

1. native 释放 GIL 的多核伸缩真实存在（5.87x@12 并发），且首个真实任务（Modbus RTU 帧解析）端到端收益 2.83x–9.71x（≥8 寄存器帧）；
2. **收益高度依赖流量形态**——工作包络（帧 ≥21 字节路由原生）只在平均意义上正确；逐任务类的最优路由会随设备与负载漂移（同一条规则下，有的任务类走原生赚 5x，有的几乎打平甚至倒挂）。

包络规则覆盖了「帧长 vs 固定地板」这一主关系，但**逐任务类的均值差异是规则写不出、只有运行期实测可见的**：静态规则按统一阈值路由，学不到"这个任务类走原生更亏"。需要一层**在线自学的路由决策**：逐任务类维护两条臂（原生通道 / Python 通道）的实测收益统计，按 ε-greedy 选择并随每次执行更新——即 multi-armed bandit（多臂老虎机）。

**维护者决定（2026-10-09）**：跳过此前规划的 ML 线，直接以 bandit 实施本能力。理由：

- 决策空间小（决策 2 臂、无跨类泛化需求、无多任务混跑场景），contextual ML/softmax 的表达力收益不存在；
- bandit 在线自治：**不需要训练项目、不需要特征日志导出、不需要权重档案**——之前延后的主要成本全部消失；
- 决策 μs 级（字典查询 + 随机数），与关闭时零影响的小改动量同级；
- 随时可以硬回滚：`adaptive:enabled=false`（默认）即整体停用。

## What Changes

- 新增 `zoo_framework/core/adaptive/` 模块：在线 ε-greedy bandit 决策层
  - `EpsilonGreedy`: 逐任务类两臂统计（均值增量式更新 + ε 探索），决策 O(1)
  - `BanditPolicy`: 逐 worker 决策入口（决策记录 + 奖励观测 + 统计更新）
- 新增 `DualArmWorker` 基类（workers 层）：用户子类声明 python/native 两条执行体，基类在 `run()` 生命周期内闭环「决策 → 双臂计时 → 更新统计」，调度内核零改动
- 新增参数键族 `adaptive:*`（`adaptive:enabled` 默认 **false**，lazy import 纪律同 `native:*`）
- **不改变**静态调度为缺省行为：关闭时框架一切如旧（零回归路径）
- 框架内零新第三方依赖（纯 stdlib：`random`/`threading`）

## Capabilities

### New Capabilities

- `adaptive-scheduling`: 逐任务类的在线自学路由决策。SHALL 在 worker 自身执行生命周期内决策双臂、观测实测时长奖励并增量更新统计，SHALL 在关闭/无统计/异常时退回静态默认路径，MUST NOT 在关闭时改变既有调度行为，MUST NOT 侵入 `WorkerDispatchCore` 语义。

### Modified Capabilities

无——`worker-scheduling` / `scheduler-model` / `native-task-execution` 的既有 REQUIREMENTS 不变；自适应层是叠加在 User Worker 生命周期内的观测/决策层，dispatch 仍经 `WorkerDispatchCore` 单一结算收口，结算语义不变。

## Impact

- **代码**：新增 `zoo_framework/core/adaptive/`（新模块）、`zoo_framework/params/adaptive_params.py`、`params/__init__.py`（导出）、`zoo_framework/workers/` 新增 `DualArmWorker` 基类
- **接线点**：**零内核改动**。决策/更新逻辑全部在 `DualArmWorker` 自身生命周期内闭环，`WorkerDispatchCore` / waiter / 调度模型无感知
- **依赖**：框架内零新第三方依赖（纯 stdlib）
- **测试**：`tests/test_adaptive_scheduling.py`（决策统计、ε 探索分布、双臂计时、奖励更新、fail-open、关闭零影响、CARRIERS 登记）
- **风险落点**：统计精度（增量均值 + ε 探索是标准形态）；worker 类型只有显式声明双臂时才参与决策（不猜测——普通 Worker 不被 bandit 无故接管）
- **与 native 线的关系**：native 臂的可用性 = `native:enabled` + 扩展可用性（经 `NativeAdapter` 握手）；`DualArmWorker` 声明了原生臂但 native 未启用/扩展缺失时，按 `native-task-execution` 的显式拒绝路径执行（不静默回退到 python 臂——静默回退会把「错误配置」伪装成「正常决策」）

---

## 延后记录（历史脉络，2026-10-09 早些时候）

本变更曾按 ML 方案（离线训练 softmax + 特征日志导出 + 权重档案）完成完整规划，随后维护者决定延后整条 ML 线（理由：包络规则已覆盖首个二元决策、特征空间小、链路成本大）。同日重新评估后**改为 bandit 方案重开**，ML 线**不再推进**（维护者指示）。

**导出机制结论的归宿**：ML 线的「特征日志导出机制是必要前提」这一结论**随 ML 一并撤销**——bandit 在线自治，无需任何数据导出与训练项目。该结论不再进入任何活跃规格；若未来 ML 线重启，从 git 历史本文件可完整恢复 ML 规划与导出机制设计（结算点 JSONL 配对导出方案 A 候选、train/serve 一致性硬约束、事件管道/聚合 API 两形态否决理由）。
