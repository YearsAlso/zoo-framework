## Purpose（本变更新增条款）

策略解析的缓存化：按 Worker 缓存三段解析结果，语义逐项不变。

## ADDED Requirements

### Requirement: 策略解析结果 MUST 按 Worker 缓存且 MUST NOT 改变三段解析语义

调度内核 SHALL 按「Worker 名 + 属性」缓存周期 / 相位 / 超时的三段解析结果（自报 → 按 Worker 名覆盖 → 全局默认），MUST NOT 在每轮调度中对同一 Worker 重复查询参数。缓存 MUST NOT 改变任何一段的取值语义：falsy 的已解析值（`0` / `False` / `""` / `None`）MUST 作为**有效结果**命中，MUST NOT 被判定为未命中而重新解析或穿透到下一段。缓存 MUST 在以下三个入口失效：调度列表整体替换、同名 Worker 重新注册、内核复位（停机清理）。

#### Scenario: 同一 Worker 的解析只查询一次参数
- **WHEN** 对同一 Worker 连续多轮解析周期/相位/超时，且期间未发生列表替换或重注册
- **THEN** 对 `ParamsFactory` 的覆盖键查询每属性只发生一次，后续轮次读缓存且返回值一致

#### Scenario: falsy 的解析值是有效缓存
- **WHEN** 某 Worker 的覆盖配置显式为 `0`（如 `phase: 0`），解析后被缓存
- **THEN** 后续解析直接得到 `0`，不会因真值判断而重查或回落到全局默认

#### Scenario: 重注册与复位使缓存失效
- **WHEN** 发生调度列表整体替换、同名 Worker 重新注册、或内核 `clear`
- **THEN** 相应 Worker（或全部）的缓存条目作废，下一次解析按新的参数配置重新求值
