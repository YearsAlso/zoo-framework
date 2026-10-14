# Design: fix-result-reactor-name-filter

## Context

见 proposal.md。相关事实：

- `BaseWorker.name` = `registry_name` + `_<num>`（`num` 由 Worker 实例持有，注册时确定）；
- `BaseWorker.run()` 此前只把 `self.name`（带序号）写进 `WorkerResult.worker_name`；
- `WaiterResultReactor.accepts` 用等值比较把过滤器字段（调用方按**注册名**填写）与
  带序号的实例名对撞，恒不匹配。

issue 给出两个可接受方向：① 给 `WorkerResult` 增加不带序号的字段、过滤器比它；
② `accepts` 改成"注册名匹配或前缀匹配"，并把语义写进文档。

## Goals / Non-Goals

**Goals**
- 按注册名筛选能收到该 Worker 的结果（任意实例序号）
- 筛选仍是**真过滤**：其他 Worker 的结果进不来，且不是前缀匹配
- 向后兼容精确实例名与 `None`（全收）
- 失败结果（#228）同样可被该过滤器筛选

**Non-Goals**
- 不做按类名 / 按通道 / 按运行标识的筛选入口（`run_id` / `session_id` 已在结果上，
  需要者自行过滤）
- 不改 `EventReactorManager.get_reactor` 的**响应器名**过滤（那是按 reactor_name 过滤，
  与 Worker 名无关，语义本就不同）
- 不做"注册名 → 多实例"的展开或通配符

## Decisions

### D1: 身份候选集匹配，而非单一字段等值比较

`accepts` 收集结果的身份候选（`registry_name`；`worker_name` 去尾部 `_<num>`；
`worker_name` 本身），与过滤器取交集判非空。三个来源各有职责：

- `registry_name`：**规范来源**，由 Worker 显式提供，回答"这个结果属于哪个注册名"；
- 去后缀形态：**兜底**，结果若由框架外构造（没有 `registry_name`）仍可被注册名筛到；
- `worker_name`：**兼容**，既有用 `ok_1` 的绕法继续可用。

只做 ①（加字段）会在框架外构造的结果上留洞；只做 ②（只去后缀）则把"身份"降级为
"对名字做字符串手术"，且无法在文档里说明清楚了然。两者合并的代价是匹配输入变多，
以"精确匹配 + 回归用例锁死前缀陷阱"兜住。

### D2: 精确匹配，不做前缀匹配

issue 的 ② 提到"注册名匹配或前缀匹配"。**不采用前缀匹配**：`ok` 前缀会连 `ok2` 的结果
一起收下，把"筛选"变成"过度放行"（调用方之所以自己写 `startswith`，是因为等值比较完全
失效；框架没有理由把这个过度放行的绕法固化成契约）。用例
`test_filter_is_not_a_prefix_match` 锁死该边界。

### D3: 去后缀只去一层，且要求前缀非空

`_ORDINAL_SUFFIX_RE = r"_\d+$"` 只剥离**一层**尾部序号（`ok_1_1` → `ok_1`），不反复
剥离——反复剥离会把注册名里的数字段吃掉。剥离结果为空时（如名字恰为 `_1`）不加入候选，
避免"空前缀匹配一切"。

## Risks / Trade-offs

- [注册名以 `_<数字>` 结尾的身份歧义] → 见 proposal 的"已知限制"；歧义来自既有命名方案，
  改命名方案属 BREAKING，超出本变更范围，记为待维护者裁决项。
- [身份候选集变多可能放行意外结果] → 三个来源都是**精确**串比较，无通配；前缀陷阱与
  "别的 Worker"两条负例都有用例。
- [`worker_names` 语义从"实例名"变为"注册名"（并兼容实例名）] → 尚无按实例名筛选的
  正当用例（序号不可预知），且旧写法仍被接受，兼容风险为零。

## Migration Plan

1. 合入即生效：`worker_names = ["ok"]` 由"恒不匹配"变为"按注册名匹配"
2. 需要精确到某一实例的调用方继续填 `ok_1`
3. 回滚 = revert 单个变更提交

## Open Questions

- 注册名以 `_<数字>` 结尾时的身份歧义是否值得引入独立的实例标识（如 `instance_id`）？
  属命名方案层面的设计分歧，列出待维护者裁决，本变更不改。
