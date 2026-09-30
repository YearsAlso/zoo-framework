## Why

上一个变更（`fix-container-spec-baseline`）把一条为假的全称断言收窄，并在要求正文里**手列**了一份"已知欠债"载体清单——三处。那份清单**不完整**，而写法却像穷举：

| 出处 | 内容 |
|---|---|
| 要求正文 | 列 3 处：`WorkerRegistry._global_registry`、`EventReactorManager.reactor_map`、`EventChannelRegister._channel_map` |
| 实测（按"测试是否必须为它单独复位"这一客观判据扫描） | **至少 6 处** |

漏掉的第一处由并行会话查出：`zoo_framework/reactor/event_reactor_req.py:196` 的模块级 `_channel_manager = ChannelManager()`（**导入时即实例化**，其 `_channels` / `_reactor_channels` 由 `tests/conftest.py` 单独复位）。另两处是 `config_funcs`（`@configure` 注册表）与 `params` 解析缓存——由 `tests/test_scaffold_cli_contract.py` 的清理单独处理。

**关键不是"漏了一处"，而是这个写法必然漂移。** 而且**复位逻辑本身也是分散的**（`conftest._reset_registries` + `test_scaffold_cli_contract` 的清理），所以连"照着复位代码抄一份清单"都做不到——没有单一权威清单可抄。

同一类缺陷在并行会话的 `docs/structure.md` 里也出现了（该节标题写着"有三类状态会活过单个用例"，实际不止三类）。两处是同一个错误：**把"我数过"写成了断言，而数错了。**

## What Changes

- **删掉**要求正文里的手维护载体枚举，改为：
  - 载体判据写成语义明确的**可验证判据**——"是否需要在测试中单独复位"，而不是主观判断它"该不该"进容器
  - 载体 MUST 通过**代码内可 grep 的锚点**标示
  - 规范正文 MUST NOT 依赖手维护的枚举（并写明本要求首版正是因此成为缺陷——把教训留在原地）
  - **两个权威来源**，互为交叉核对：代码内锚点（`grep -rn "已知欠债" zoo_framework/`）与**执行复位的测试辅助**（`tests/` 中清除进程级状态的代码）。后者是复位事实本身、先于任何标注存在，故不依赖"有人记得去标"
  - **首轮必须一次性播种**：所有**已知**载体一次打上锚点；其后新发现的在发现时补锚。MUST NOT 以"增量发现"为名让起点停留在一份不全的清单上
- **播种锚点**：把已知的全部需单独复位的载体一次性标注（范围按上述客观判据）

**Non-goals**

- **不迁移**任何容器外载体（与上一个变更一致；类属性与实例的收编量级不同，属独立变更）
- **不改**并行会话的 `docs/structure.md`——那是它的文件，它已确认会按"去枚举"改（**不是**按"更精确的枚举"改，后者只是在造一份更长的枚举）
- 不改变任何运行时行为（除注释外不动实现）

## Impact

- 受影响 spec：`scoped-container`（1 条修改要求）
- 受影响代码：仅为已知载体补锚点注释（无行为改动）
- 受影响文档：无（`docs/structure.md` 由并行会话按其自身判断改）
