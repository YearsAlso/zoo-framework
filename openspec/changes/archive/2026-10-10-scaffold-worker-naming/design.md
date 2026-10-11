# 技术设计：scaffold-worker-naming

## 现状梳理

`_worker_names(worker_name)` 返回 `(f"{worker_name}_worker", f"{worker_name.title()}Worker")`。
`str.title()` 的问题：它按"连续字母块"找边界，**下划线不是字母块的结束**——但对于
`my_task`，`title()` 实际得到 `My_Task`（下划线后的 t 被当新词首字母，下划线本身
保留）。类名于是带下划线，不是 Pascal 也不是 Snake，是第三种东西。

**注册名现状**：脚手架入口的 `WORKERS` 元组是 `("类名", 类)`，注册名=类名字符串
（`master.register_worker(name, worker_class)` 的第一个参数）。本变更**不改注册
机制**——让注册名有规则（=类名），三处一致由命名规则统一保证。

## D-Rules：命名规则（写入规则的正文，代码即其实现）

输入：已通过 `_validate_worker_name` 的合法 Python 标识符（lower() 已在
`zfc.__init__` 中施加）。

1. **主体**：输入原样作为名称主体，不做后缀剥离/添加（输入已含 `worker` 时类名
   是 `SampleWorkerWorker`——名字是使用者语义，工具不代为裁剪；`worker` 后缀
   本身出现在合法标识符里只提醒使用者，不改变规则）；
2. **分段**：按下划线 `split('_')`，**空段跳过**（`x__y` → XY、`_x` → X，
   前导/连续/尾随下划线都不产生空段首字母）；
3. **每段大写化**：`segment.capitalize()`——段内仅首字母大写，其余**原样保留**
   （`v2e` → `V2e`，`task2` → `Task2`；不用 `title()`，它会把段内数字后字母
   重新大写）；
4. **拼接 + Worker 后缀**：`"".join(...) + "Worker"`；
5. **结果必为合法标识符**：输入合法 ⇒ 每段首字符非空段下划线且为字母或下划线
   开头的串……严格说 `_x` 是合法标识符，分段后首段为空被跳过，`X` 合法——
   规则自证闭合；`a` → `AWorker`。

backslash/Unicode 标识符（`他store` → `他storeWorker`）：Python 合法，规则自然
覆盖（capitalize 对中文首段无操作），不特殊处理——合法输入的产物必须可用，规则
只增不改字符集。

## 决策

### D1: `_worker_names` 单点实现，不改模板与接线

模板用 `class_name` 变量渲染，`_wire_worker_into_main` 按整行判重——两者对类名
的**来源**无感知，改 `_worker_names` 一处，文件名→导入行→注册条目三处自动一致。
不在模板里做名字修正（模板没有输入形状信息）。

### D2: 示例 Worker 零改动（#110 产物在新规则下不变）

`DEMO_WORKER_NAME = "sample"`，新规则产出 `SampleWorker`，与 `main_template`
静态预置的 `SampleWorker` 字样**逐字相同**——这是 #110 落地时就按新规则预留的
形态（当时为对齐既有 title 规则手工选了 `sample`）。本变更把这条"手工对齐"
变成"规则推导"，模板/测试/`[sample_worker] tick` 输出形态零改动。

### D3: `str.title()` → `split('_')` + `capitalize()`，不用 `str.title().replace('_','')`

后者对 `v2e` 会产出 `V2EWorker`（title 把数字后的字母也大写），违反段内语义；
显式分段是规则的可读实现， MIL 8 行。

### D4: 测试翻转 5 处 `My_TaskWorker` 断言

`test_entry_registers_declared_workers` / `test_worker_module_imports` /
`test_worker_instantiable` / `test_registered_worker_is_scheduled_and_executed` /
`test_worker_module_is_reachable_from_entry`：类名字面量翻转 + docstring 标注
"行为意图变更：#112"。拒绝行为用例零改动。

### D5: 新增边界用例挂 `test_legal_name_yields_legal_class_name` 参数表

现有参数表 `["my_task", "task2", "_private", "a"]`，加 `x__y` / `v2e`，并把断言
升级为「PascalCase(输入) + Worker 逐字相等」——不是宽松的 `isidentifier()`。
新增 `order_sync`→`OrderSyncWorker` / `my_task`→`MyTaskWorker` 的端到端两例。

## 风险

- 用户已按旧名写了 `from workers.my_task_worker import My_TaskWorker` 的项目，
  重新生成同名文件仍落同名文件（文件名规则未变），类名变 `MyTaskWorker` 但
  旧 import 行是用户手写的，框架不回收——风险与"工具不代为改用户文件"对齐。
- `_private` → `PrivateWorker`（首段空跳过后首字符大写，结果不再以下划线开头）
  ——类名合法且符合 Pascal 约定，是改善而非回归。
