## 1. 规范正文去枚举

- [x] 1.1 删除正文里的载体枚举，改为机制表述。**已完成**：正文不再列任何载体清单；并写入一句教训——"本要求的首版正是因手列载体不全而成为缺陷（手列三处、实测至少七处）"，留在原地防复发
- [x] 1.2 判据写成可验证形式（"测试是否必须为它单独复位"），并写明 MUST NOT 以主观判断"它该不该进容器"代替。**已完成**：判据可从复位代码直接读出，不依赖任何人（包括我）的判断
- [x] 1.3 指明**两个**权威来源并说明为何不是只信其一。**已完成**：代码内锚点 + 执行复位的测试辅助；并写明"锚点依赖有人记得去标，而复位代码是事实本身、先于任何标注存在"
- [x] 1.4 写入播种要求。**已完成**：三句都在（已发现的一次性播种；其后新发现的发现时补锚；MUST NOT 以增量发现为名让起点停留在一份不全的清单上）

## 2. 播种锚点（范围 = 判据内的载体）

- [x] 2.1 补齐缺失锚点。**已完成，且比任务书里估的多**：任务书写"六处"，实际播种**七处**——在实现过程中按判据继续扫，又发现第七处 `ParamsFactory.config_params`（`core/params_factory.py` 的**类属性**，由 `tests/test_config_resolution.py` 单独 monkeypatch）。七处为：`worker_registry`（模块级惰性单例）、`event_reactor_manager.reactor_map`（类属性）、`event_channel_register._channel_map`（类属性）、`event_reactor_req._channel_manager`（模块级、导入时即实例化）、`configure.config_funcs`（模块级注册表）、`aop/params.config_params`（模块级解析缓存）、`params_factory.ParamsFactory.config_params`（类属性）。**"估六处、实得七处"本身就是本变更论点的又一次复现**：手数不可靠
- [x] 2.2 以复位代码为事实源逐条比对。**已完成**：`grep -rl "已知欠债" zoo_framework/` = **7 个文件**；从复位代码独立导出 = `conftest._reset_registries`（`reactor_map` / `_channel_map` / `WorkerRegistry._*` 四项缓存 / `channel_manager._channels`、`._reactor_channels`）+ `test_scaffold_cli_contract` 的清理（`config_funcs` / params 解析缓存）+ `test_config_resolution` 的 fixture（`ParamsFactory.config_params` / `aop.params.config_params`）= **7 类载体**
- [x] 2.3 不把"设计如此"的模块级对象误标成债。**已完成**：扫描出的 `plugin_manager`、`EventProvider._eventChannelRegister`、`SingleFIFO.index_list`、`utils/thread_safe_dict._lock`、`core/container/registry._process_container`（后者**就是容器本身**）等均**未**加锚——它们不由任何测试单独复位，不落在判据内。多标会稀释锚点含义

## 3. 验证与归档

- [x] 3.1 `openspec validate --strict` 与 `--specs` 通过。**已完成**（初次校验**失败过一次**，见下方披露）
- [x] 3.2 全量回归与 CI 口径质量门。**已完成**：**660 passed / 0 failed**（与变更前持平——本变更不含行为改动与新增用例）；`ruff check zoo_framework` 通过；`ruff format --check` 94 files unchanged
- [x] 3.3 未夹带范围外改动、且未改运行时行为。**已完成**：四个代码文件的**非注释改动行均为 0**；改动面 = 7 处锚点注释 + 本变更的 openspec；无依赖变更
- [x] 3.4 **播种完整性独立复核**。**已完成**：用**不依赖锚点**的来源（复位代码）独立列出载体，与锚点集合比对——**两集合相等，7 ↔ 7**（排除 `framework_container()`，它本身就是容器、不是债）。未用"grep 后看数量"自证

## 披露：初次校验失败，而且是同一类错误的第三次

本变更的 delta 初版**校验失败**，报错为：

> MODIFIED "框架自身的进程级共享 MUST 被显式归类" omits scenario(s) the current spec still has: "已知欠债被记录而非被当作已满足". Copy them into the MODIFIED block (a MODIFIED requirement replaces the whole block, so archive refuses to drop them).

原因：`MODIFIED` 替换**整个 requirement 块**，故必须带上基线里现存的所有 Scenario，而我改写时漏带了一条——**我又一次手维护了一份清单（这次是"要带的 Scenario"）并漏了一项**。这已是同一类错误的**第三次**：① 全称断言对现状为假；② 欠债载体枚举不全；③ MODIFIED 漏带 Scenario。

三次都由**外部检查**发现（前两次是并行会话、这次是 `openspec` 校验器），没有一次是我自查发现的。这条披露本身就是本变更"用机制替代手维护清单"的最强论据——**我的手维护清单已经被证伪三次，而校验器与复位代码各自一次就抓准了**。
