# 任务表（重取基线后）

> 本表已于 **2026-09-30** 按实测重取基线重写。原始表把若干前提写成了已完成或未变，实测不符；
> 下面逐条标注 **[已完成（他处）]** / **[前提已变]** / **[新增]**，并在文末留「重取基线结论」。
> 重写的原因与方式见文末最后一节——它是本仓库这一轮反复出现的同一族问题的又一次实例。

## 1. 前置：重取基线

- [x] 1.1 确认 `fix-runtime-defects` 已落地。**部分成立，原始断言有误**：
  - `fix-runtime-defects` 确已归档（`openspec/changes/archive/2026-09-27-fix-runtime-defects/`）✓
  - 原断言「`reactor/event_reactor.py` 的 `int`/`EventPriorities` 不兼容错误不再出现」→ **该错误确已消失**，但该文件**仍有 3 条别的错误**（`29:43`、`32:46` 的 `Function "builtins.callable" is not valid as a type [valid-type]`——用了小写 `callable` 而非 `Callable`；`120:17` 的 `"None" not callable [misc]`）。**"不再出现"成立，但"该文件干净"不成立**，原表把两者混为一谈
  - 原断言「`event/__init__.py` 的 `__all__` 元素类型错误不再出现」→ **不成立，该错误仍在**（`event/__init__.py:5:1: Type of __all__ must be "Sequence[str]", not "list[type]"`——`__all__` 里放的是**类对象**而不是字符串）。这条属于本变更要修的范围，`fix-runtime-defects` 未涉及
- [x] 1.2 重取类型错误基线并归档为三类。**已完成，实测结果与原始假设有出入**：

  **基线：`mypy zoo_framework --explicit-package-bases` → 82 errors / 30 files（checked 94 source files）**

  | 错误码 | 条数 | 归类 |
  |---|---|---|
  | `arg-type` | 12 | 真实缺陷 |
  | `no-any-return` | 10 | 注解缺失（被调方无注解，返回 Any） |
  | `unreachable` | 8 | **逐条判定**（多为其他错误的后果，也可能是注解缺失导致收窄为 `Never`） |
  | `assignment` | 8 | 真实缺陷 |
  | `var-annotated` | 7 | 注解缺失 |
  | `union-attr` | 7 | 真实缺陷（可能为 None 的属性访问） |
  | `valid-type` | 6 | 真实缺陷（小写 `callable` 当类型用） |
  | `no-redef` | 6 | 真实缺陷（重复定义） |
  | `call-overload` | 5 | 真实缺陷 |
  | `misc` | 4 | 混合（含 `__all__` 类型、`None not callable`），逐条判定 |
  | `attr-defined` | 2 | 真实缺陷 |
  | `unused-ignore` | 1 | 清理（多余的 `type: ignore`） |
  | 其余 6 个码各 1 条 | 6 | 逐条判定 |
  | **合计** | **82** | ✓ 与实测总数一致 |

  **分类汇总：注解缺失 17 / 真实缺陷 ~51 / 逐条判定 ~14（`unreachable` 8 + `misc` 4 + 其余零散）/ 第三方存根缺失 0**

  **两处改写原假设的结论**：
  1. **「第三方存根缺失」这一类恒为空**：`pyproject.toml` 的 `[tool.mypy]` 里 `ignore_missing_imports = true`，所以 mypy **从不报告**缺存根。原表把这一类当成有活儿可干，实际它**按配置为空**。真正可做的是**反向动作**——为实际用到的依赖补存根、再收窄这个全局忽略（见改写后的 3.3）。
  2. **错误分布集中在少数文件**：`state_machine_work.py` 8、`event_channel_manager.py` 8、`core/container/registry.py` 5、`base_waiter.py` 4、`container.py` 4。**其中 `registry.py` / `container.py` 是本轮 scoped-container 新增的文件**——即**新代码也带进了类型错误**，本变更要连它们一起清零（原表未预期这点）

## 2. 修复类型检查的执行路径

- [x] 2.1 删除仓库根的空 `__init__.py`；验证：`grep -rn "^from zoo import\|^import zoo$" zoo_framework/ tests/ example/` 无结果，且 `python -m build` 后 `twine check dist/*` 通过。**[前提确认]**：该文件仍在且仍被跟踪（0 字节，日期 2023-07-01），是 `mypy` 因模块名映射冲突而中止的直接原因（实测报 `Source file found twice under different module names`）。**已完成**：`git rm __init__.py`（从索引与磁盘一并移除）。`import zoo` 引用检索 **无结果 ✓**。**构建验证已完成**：装上 `hatchling` 后 `python -m build --no-isolation --outdir <干净目录>` 产出 `zoo_framework-0.5.3b0.tar.gz` 与 `.whl`，对新产物 `twine check` **两项均 PASSED ✓**。**这次验证躲过了一个假通过，值得记下**：第一次直接跑 `twine check dist/*` 也报 PASSED，但 `dist/` 里是 **2023 年的旧产物**（`0.0.0` / `0.4.2` / `0.5.1`），而当时 `python -m build` **因缺 `hatchling` 已失败**——即那次"通过"验证的是**旧文件**，与本次改动无关。故改为构建到**干净目录**再校验，避免旧产物把假通过喂进来。这也说明"命令返回 PASSED"与"验证了本次改动"是两件事
- [x] 2.2 从仓库根执行类型检查，确认不再因模块名映射冲突而中止；验证：输出中出现被检查文件数汇总，且不含 `errors prevented further checking`。**已完成**：裸跑 `mypy zoo_framework`（**不带** `--explicit-package-bases`）现输出 `Found 82 errors in 30 files (checked 94 source files)`，且 `found twice` / `errors prevented further checking` 命中 **0 处** ✓ —— 说明那个 flag 此前只是绕过手段，删根 `__init__.py` 才是正解（与 design D1 一致）
- [x] 2.3 确认被检查文件数覆盖框架包全部源文件；验证：报告的文件数等于 `find zoo_framework -name "*.py" | wc -l`。**已完成**：mypy 报 **94**，`find` 计数 **94** ✓ 相等

## 3. 清零类型错误

- [ ] 3.1 修复归类为"真实缺陷"的错误（~51 条）；验证：该类别归零，且相关回归用例仍通过。**进行中（第一批已提交）**：82 → **68** errors。已清零三类：`valid-type` 6→0（`builtins.callable` 当类型用、`list[X] or None` 这种非法注解）、`no-redef` 6→0（`event_channel_manager` 各分支重复声明 `reactors`）、`attr-defined` 2→0（`threading._active` 改为 `getattr`，不加 ignore）。**一处值得单记**：修 `get_channel_reactors` 的返回类型时（`list[EventReactor] or None` → `| None`）**暴露了一个真实缺陷**——原注解因 `or` 短路求值实际等价于 `list[...]`，于是 mypy 看不见 `None`；改正后 `event_worker.py` 立刻报出两条（对可能为 `None` 的返回值直接 `len()`／迭代）。该处原以 `len(reactors) == 0` 写得，`None` 会抛 `TypeError` 而被上面的 `except` 兜成"查询响应器失败"——**既是用异常做控制流，又把"无匹配"错报成"查询失败"**；改为 `if not reactors:` 后两者同义、路径也统一。**这正是类型门禁的价值：一个非法注解一直在掩盖下游的 None 处理缺口**。
**第三批（已提交）**：61 → **53** errors，且**零新增错误**。本批专治 `unreachable`（8→1）与随之暴露的 `assignment`/`no-any-return`，**全部落在同一个根因上**：**注解（或推断出的类型）写成非 Optional，而代码里有 `is None`/真值防护**——防护正是"它是 Optional"的证据。**关键在于必须先判定哪一侧错**，判据是**读实现**：
  - **注解错、防护对 → 放宽注解**：`EventChannel.pop_value` 的 `-> EventNode` 与基类 `BaseFIFO.pop_value` 的 `-> EventNode | None` 相矛盾（基类已经写明 Optional，子类把它丢了），放宽后 `event_worker` 那处 `if event_node is None: break` 由"不可达"变回可达，同时消掉该文件的 `no-any-return`。`state_node` 的 `effect: types.FunctionType`（参数）与 `base_worker` 的 `_destroy_func`（被推断成 `None`）同理放宽。
  - **注解对、防护是死码 → 删防护**：`EventChannelRegister.get_channel` 的实现是"未命中就地创建再返回"，**不可能**返回 None，故 `register` 里的 None 分支与 `event_worker` 里的 `if channel is None: continue` 都是死分支，已删（零行为改动）。`event_channel_manager` 里 `raise` 之后的 `return None` 亦为死语句，已删。
  - **`Callable` 的导入位置**：`base_worker` 的属性注解**不在运行期求值**（已实测：`self.x: NoSuchName = 1` 不抛 NameError），而函数签名注解**会**求值——这正是 ruff 只对该文件报 TC003 的原因。故按仓库既有的 `TYPE_CHECKING` 写法（`state_node.py` / `event_worker.py` 已有先例）移入，**实测不影响运行期**（660 passed）。**没有盲从 linter 的建议**：先验证"移入是否安全"，再采信。

**本批另记两条独立发现（都不靠猜修）**：
1. **`BaseWorker._destroy_func` 从未被赋值**：全仓库（含 tests/example）只有 `= None`，没有任何地方给它赋可调用对象 → `__del__` 里那条销毁路径**恒不执行**。类型上已按 `Callable | None` 如实注解（消掉错误），但"钩子从未接线"是独立缺陷，**不**靠删掉防护来掩盖。
2. **`master.py:283`：`change_waiter` 恒抛异常**——`__init__` 必设 `self.waiter`，故 `if self.waiter is not None: raise` 恒真、`self.waiter = waiter` 不可达，即**该方法永远无法完成它的职责**；且**全仓库零调用点**。意图不明（是"禁止替换"的设计，还是"应当允许替换"的写错），**故只记录、不改**——猜一个然后删掉 raise 或删掉赋值，都是在替作者决定语义
**第四批（已提交）**：53 → **48** errors。**本批修的是本轮 `scoped-container` 新增代码自身的类型错误**——即**新代码也带进了错误**（重取基线时 1.2 已实测到 `container.py` / `registry.py` 在列）：`container.py` 3 条 + `registry.py` 1 条。根因同族（"交给 mypy 从首条分支推断 ⇒ 变量被钉窄"）：`product` 在三条分支里分别为 `_Constant`／工厂／类，推断首条即错，改为**显式声明** `product: Callable[[], Any]`；`replace` 里的三元表达式改为 if/elif，让检查器看得见"此处必非 None"。**一处工具冲突值得单记**：`registry.py` 安装 `__new__` 时，mypy 判直赋值类型不符（typeshed 把 `__new__` 标成重载函数），而改成 `setattr(cls, "__new__", ...)` 又被 ruff 的 **B010**（不要用 setattr 传常量属性名）拦下——**两个工具要求相反、无法同时满足**。最终保留直赋值 + **定向** `type: ignore[assignment]` 并写明原因：它压制的是**两个工具的对立**，而非一处本可修好的不匹配（符合 3.4 的验收口径）；该 ignore 未被 `warn_unused_ignores` 判为多余 ✓（当前唯一那条 `unused-ignore` 在 `utils/structured_log.py:15`，属既有、与本批无关）
**第五批（已提交）**：48 → **41** errors，`union-attr` 7→0，零新增错误。**本批是真正的空处理缺口修复（有行为含义）**，且**每处的判据都来自代码自身已有的证据**，不是我选的：
  - `core/master.py` 的 `_setup_svm`：**同文件其余四处取用 `svm_worker` 都判了空**（226/306/381/399），只此处漏 → 未启用 SVM 时原先会直接 `AttributeError`。补上与其余各处一致的判空。
  - `statemachine/state_machine_manager.py` 的 `remove_state`：原先"先 `get_state_node(key) is None` 判空、**随后再取一次**"，而 map 是 `ThreadSafeDict`——两次取值之间节点可能已被并发移除，**原本存在真实空窗**（届时 `node.get_value()` 会抛）。合并为一次取值，同时消掉窗口与类型错误。
  - `core/params_factory.py` 的 `load_exports`：原写成 `type(export_files) != type([])`，该写法**不构成检查器可识别的收窄**（故基线一直报）且会拒绝 `list` 子类；改为 `isinstance(..., list)`——配置来自 JSON、产出精确 list，本场景等价。
  - `utils/structured_log.py`：两处**运行期本就正确**（`hasattr(None, "bind")` 为 False），但静态检查无法从 `hasattr` 收窄 `Any | None` → 补显式 `is not None`，**行为不变**，只让既有防护可见。**该模块经实测全仓库零引用**（未从 `utils/__init__` 导出、无任何调用点）——"是否该删除"是独立决定，**不借本批顺手删**（与 `_destroy_func`/`change_waiter` 同一克制）
**第六批（已提交）**：41 → **36** errors，`arg-type` 12→7（余 7 条同属一族，见下）。本批**修掉两个真缺陷**（都属"类型检查抓出了运行期错误"）：
  - `statemachine/state_scope.py` 两处 `LogUtils.error(self.__class__, f"State is not exist, key: {key}")`——**参数写反了**：该函数签名是 `(message, cls_name=None)`，而这里把**类**当 message、把消息当 cls_name 传，于是**日志里打出的是类对象而不是那条消息**。已按签名交换。
  - `statemachine/state_node.py` 的 `_effect_list` 注解为 `list[StateEffect]`，但代码往里存的是**函数**（`add_effect` 的 `isinstance(…, types.FunctionType)`、`_perform_effect` 的 `gevent.spawn(effect, …)` 都是证据），而 **`StateEffect` 没有 `__call__`** → 那个类型**根本不可能**被 spawn 调用。改为如实的 `list[types.FunctionType]`（并移除因此变为未使用的 `StateEffect` 导入）。**另核实**：全仓库**无人**给 `StateNode(effect_list=…)` 传参，故改构造参数注解无副作用。
  - `core/container/container.py` 一条（本变更自己的代码）：`qualified_name(registered_type)` 的实参是 `type | None`，而该路径由 `_resolve_registered_type` 保证非 None；补显式断言把这条不变量变成检查器可见的。
**剩余 36 条的结构**：`arg-type` 7（**同属一族：`@params` 把 `ParamsPath` 属性在运行期改写成字面值，静态类型却是 `ParamsPath`**，见下）＋ `no-any-return` 10 ＋ `call-overload` 5 ＋ `misc` 4 ＋ `assignment` 4 ＋ 零散 6（含 `master.py:283` 那条**已记录的**发现与 `structured_log.py:15` 那条**既有**的 unused-ignore）。**`@params` 一族需要一个设计决定**：全仓库有 14 处 `X = ParamsPath(...)`（`worker_params` 9 / `event_params` 2 / `log_params` 2 / `state_machine_params` 1），它们在静态上是 `ParamsPath`、运行期是解析后的字面值，故凡把它当 `str`/`int` 用的地方都报类型错。可选修法：**给 `params_path.py` 加一个按 `default` 推断返回类型的薄封装**（`param(value, default: T, aliases=None) -> T`，运行期仍返回 `ParamsPath` 供 `@params` 改写，静态上就是 `T`），改 14 处声明；或在 14 处各写 `cast`。**这是范围决定，须先定再做**
**第七批（已提交）**：36 → **21** errors，`arg-type` 7→0。**用户裁定采用"类型化薄封装"**：`params_path.py` 新增 `param(value, default: T, aliases=None) -> T`——运行期仍返回 `ParamsPath`（`cast` 是空操作）**故 `@params` 的配置机制完全不变**，静态上返回类型由 `default` 推断（而 `default` 的类型本就是解析后的类型）。15 处声明改为 `param(...)`；其中 `WORKER_PERIOD` / `WORKER_PHASE` 的 `default=None` 另加显式 `float | None` 标注（`None` 可赋给 Optional，故该标注成立）。
**两处如实更正**：① 我在批内多处写"14 处声明"，**实为 15 处**——第 15 处在 `zoo_framework/templates/__init__.py`（脚手架模板），我最初的 grep 限定了 `zoo_framework/params/` 因而漏计。**又一次"查询的作用域小于我所以为的"**（同族第六次）。模板那处**不在 mypy 检查范围内**（它在三引号模板字符串里），故不是错误来源，但它是**用户复制的范本**——留旧写法会让生成的项目继续带这类类型问题，故一并改为 `param`（`docs` 那行描述也随之调整）。
② **本变更第二处工具冲突**（第一处是 `__new__` 的 mypy↔B010）：ruff 的 **UP047** 要求把 `param` 改为 PEP 695 的 `def param[T](...)`，而 **mypy 1.7.1 报 "PEP 695 generics are not yet supported"**——1.7.1 既是 pre-commit 钉住的版本、也是 CI 安装的那版。**两个工具要求相反**，故保留 `TypeVar` 写法 + 定向 `# noqa: UP047` 并写明原因（升级 mypy 才能解掉，属依赖变更、不在本变更范围）。**两处冲突同形**：都只能靠"定向 ignore + 就地说明"解决，而不是任何一方的偏好

**第八批（已提交）**：21 → **17** errors（零新增）。**根因**：`utils/thread_safe_dict.py` 的 `ThreadSafeDict` **方法全无注解**，故 `get()` / `pop()` 返回 `Any` → 凡从声明为具体返回类型的函数里返回它的结果都报 `no-any-return`（10 条）。**修法与 `ParamsPath` 同形**（用户既已裁定"把类型如实构造出来"，此处沿用同一答案）：把该类**泛型化**（`Generic[_K, _V]` + 逐方法注解，**纯注解、运行期无变化**，裸写 `ThreadSafeDict()` 仍等价于 `[Any, Any]`），再给 6 处**声明**补上类型参数（`str, EventChannel` / `str, StateScope` / `str, StateNode` / `str, list[EventReactor]` / `str, Any` ×2）。
**两处连带是正确处理而非绕过**：① `event_channel_register.get_channel` 由 `.get()` 改为 `__getitem__`——后者返回**非 Optional** 的 `V`，而该处"未命中就地创建"本就保证有值，故同时消掉 `no-any-return` 与泛型化后会出现的 `return-value`，**且不需要 cast**；② 泛型化会让**裸声明**触发 `var-annotated`（mypy 要求显式类型参数），故 6 处一并参数化——**动手前先量了爆炸半径**（6 处、4 处会报），确认可接受才做。
**第三处工具冲突，且这次是系统性的**：ruff **UP046** 要求 `class ThreadSafeDict[_K, _V]:`（PEP 695），mypy 1.7.1 不支持。加上此前的 mypy↔B010（`registry.py` 装 `__new__`）与 mypy↔UP047（`param`），**三处同根**：**钉住的 mypy 版本低于本仓库启用的 ruff 规则所假定的语法**。三处都用"定向 noqa + 就地说明"，并在 `thread_safe_dict.py` 注明：**升级 mypy 可一次解掉全部三处**（依赖变更，不在本变更范围）
- [ ] 3.2 为归类为"注解缺失"的错误补充类型注解（17 条）；验证：该类别归零，且 `pytest -q` 仍全绿。**进行中（第一批已提交）**：`var-annotated` 7→0（含模块级字典、类属性字典、`set()` 局部共 6 处）。**一处反向的教训值得单记**：`core/aop/validation.py` 的 `params_validate_map` 我一开始标成 `dict[str, list]`（"更精确"），结果 mypy 立刻报出 `validation_params` 里那处 `isinstance(valid_values, list)` 防护为 **unreachable**——即**一个更精确的注解制造了一个新错误**。原因是该注解断言"值恒为 list"，而**那处防护的存在本身就是该不变量不成立的证据**（其文档也写明会返回 False 的"类型不正确"情形）。故改为**裸 `dict`**（≡ `dict[Any, Any]`）：既消掉 `var-annotated`，又让防护保持可达，**零行为改动、零新增错误**。通则：**当代码里有针对某类型的防护时，不要用注解把该类型收窄到防护失效**——防护是作者对不变量的反证
- [ ] 3.3 **[改写]** 处理 `ignore_missing_imports`：原表写"处理第三方存根缺失"，但该分类**实测恒为空**（被配置抑制）。改写为——**为框架实际使用的依赖（click / jinja2 / gevent / pyyaml / python-dotenv）补存根，然后把 `ignore_missing_imports` 从全局收窄为按模块**；验证：全局为 false（或按模块列出例外），且 mypy 仍零错误、退出码 0。**若收窄后发现代价远超收益，须把"保持全局忽略"作为显式决定记录下来**，而不是默默不动
- [ ] 3.4 审查本次新增的每一处 `# type: ignore` 与 `cast`；验证：`grep -rn "type: ignore\|cast(" zoo_framework/` 的每一处都有相邻注释说明原因，且没有一处是用于压制本可修复的类型不匹配（逐条核对并记录）。**注**：当前基线里已有 1 条 `unused-ignore`，说明**存在多余的 ignore**，属本任务范围

## 4. 建立类型门禁

- [ ] 4.1 移除 `.github/workflows/quality.yml` 中 mypy 步骤的 `continue-on-error`；验证：临时插入一个类型错误 → 本地类型检查返回非零 → 撤销后返回零
- [ ] 4.2 移除 `.github/workflows/release.yml` 中 mypy 步骤的 `continue-on-error`，并确认发布作业依赖质量检查的结果；验证：release.yml 中发布作业的 `needs` 链包含质量检查作业。**注意**：`release.yml` 当前由**并行会话**在改（"不吞"修复），改动前须与其确认，避免两人改同一文件；实测该文件里 mypy 那处 `continue-on-error: true`（原 121 行）**仍在**，正是本任务的目标
- [ ] 4.3 按 design D3 在 `[tool.mypy.overrides]` 中对 `zoo_framework/utils/` 开启 `disallow_untyped_defs`；验证：该模块中缺注解的函数被报告为类型错误
- [ ] 4.4 确认开启单模块严格模式后其他模块的检查结论不变；验证：对比开启前后在其余模块上的错误数，二者一致（均为零）
- [ ] 4.5 确认本地与 CI 的类型检查命令逐字一致；验证：比对 `quality.yml` 的 mypy 步骤命令与本地执行的命令字符串，完全相同
- [ ] 4.6 **[新增]** 把本地 mypy 的 pre-commit 钩子从 `manual` 阶段恢复到**默认阶段**（提交时运行）。**为什么原表没有**：这条是**本变更自己的前置工作造成的**——`52d9cd4` 当时把该钩子移出默认阶段，理由是"mypy 根本跑不起来"（根 `__init__.py` + 82 条错误）。2.1–3.3 完成后那个理由消失，**若不恢复，就会出现"CI 门禁开着、本地门禁关着"**——正是 6.1 与 `ef4bed2` 存在要消除的那种本地/CI 分叉。验证：本地提交时 mypy 钩子会实际运行（而非仅 manual 阶段可跑），且一次干净提交能通过

## 5. 开发环境与锁定文件

- [ ] 5.1 按 design D4 修正 `uv.lock` 的 `requires-python`，使其与 `pyproject.toml` 一致；验证：两个文件的 Python 版本要求字符串相等。**[在途]**：`uv.lock` 当前**有未提交改动**（并行会话误触发的整份重解析：revision 1→3、`requires-python` 提到 `>=3.13`、+1110/−469），其内容**可能已满足本任务**，但该改动归属并行会话、由其用户决定去留。**本任务执行前须先与该会话确认，勿自行处理 `uv.lock`**
- [ ] 5.2 按 design D4 将 `uv.lock` 中的 `greenlet` 升级到在 Python 3.13 上有可用产物的最低版本，仅做最小改动；验证：`uv sync --frozen` 在 Python 3.13 上成功，不再出现 greenlet 构建失败。**同上：`uv.lock` 归属并行会话**
- [ ] 5.3 确认锁定文件未发生无关依赖变动；验证：`git diff uv.lock` 只涉及 `requires-python` 与 `greenlet` 相关行及必要传递依赖。**注意**：当前那份在途改动**正是**"整体重新解析"（+1110/−469），与 design D4 的"最小修正"**相冲突**；若采用它，须把"放弃最小修正"作为显式决定记录，而不是当作符合 D4
- [ ] 5.4 确认元数据安装路径仍可用；验证：`pip install -e ".[dev]"` 成功，随后 `pytest -q` 全绿

## 6. CI 作业修正

- [x] 6.1 把 bandit 参数由 `-c pyproject.toml` 改为 `-c .bandit.yaml`。**[已完成（他处）]**：由 `ef4bed2` 完成，且顺带加了 `files: ^zoo_framework/` 使范围与 CI 一致。验证方式原为 `pre-commit run bandit --all-files`；实测当前配置为 `files: ^zoo_framework/` + `args: ["-c", ".bandit.yaml"]` ✓
- [ ] 6.2 给 `.github/workflows/docs.yml` 的产物上传步骤加上与构建步骤相同的 `hashFiles('mkdocs.yml')` 条件。**[前提已变，性质从"当前必失败"降为"鲁棒性"]**：实测该不对称**仍在**（上传步骤无同条件），但 ① `mkdocs.yml` 现已提交（`1af83c5`），故条件为真、构建与上传成对执行；② **GitHub Pages 现已启用**（`gh api repos/.../pages` → `build_type: workflow`，站点 `https://yearsalso.github.io/zoo-framework/`）。所以现在**不会失败**，但将来 `mkdocs.yml` 若被移除，上传仍会带不存在的 `./site` 跑。**任务本身仍成立**（鲁棒性），但原始理由（"当前必失败"）已过期，须按新事实写入提交说明
- [ ] 6.3 让 `.github/workflows/tests.yml` 的 Python 安装步骤使用 `${{ matrix.python-version }}`。**部分已完成**：矩阵本身已是参数化（`tests.yml:20` → `["3.13"]`），但**两处仍硬编码** `python-version: "3.13"`（`:29`、`:66`）。本任务按"不再出现硬编码字面量"验收，故**仍需做**
- [ ] 6.4 修正 `tests.yml` 中引用不存在目录的 `benchmark` 作业（加目录存在性条件，或移除）。**未做**：该作业仍在（`:56`），且仍 `run: pytest tests/benchmarks/ ...`（`:75`）
- [ ] 6.5 全量复核所有 workflow 中"条件加在主步骤、未加在依赖它的后续步骤"的情形；验证：逐个 workflow 检查含 `if:` 的步骤，其下游依赖步骤均带同条件。**注**：这条是 6.2 的推广，**建议同时覆盖 `continue-on-error` 吞掉失败的情形**——`release.yml` 已实测出两处（步骤级 + 内部 `if/else`），属同一"条件加错位置"的家族

## 7. 示例与仓库卫生

- [ ] 7.1 按 design D9 修正 `example/main.py` 构造框架对象的方式（当前以整数调用，实测抛 `AttributeError`）；验证：按示例自身声明的方式运行该入口不再抛异常
- [ ] 7.2 按 design D9 修正 `example/event/demo_event.py` 从 `build.lib` 导入的问题；验证：`grep -rn "build\.lib" example/ zoo_framework/` 无结果，且该模块可被成功导入
- [x] 7.3 补齐 `.gitignore`，覆盖字节码缓存、构建输出与虚拟环境三类路径。**[已完成（他处）]**：`__pycache__` / `venv` / `.venv` / `build/` / `dist/` / `/site/` 均已存在 ✓
- [x] 7.4 把已被误跟踪的构建产物、字节码缓存与虚拟环境从版本控制索引中移除并保留磁盘文件。**[已完成（他处）]**：`git ls-files | grep -E '^(venv|build)/|__pycache__|\.pyc$'` 返回 **0** ✓
- [x] 7.5 清理只剩字节码的 `test/` 目录索引条目。**[已完成（他处）]**：`git ls-files test/` 返回 **0** ✓
- [x] 7.6 **[新增]** 同步 `zoo_framework/__init__.py` 的 `__version__`。**为什么原表没有**：实测该文件写着 `0.1.1-beta`，而 `pyproject.toml` 与 `.env` 都是 `0.5.3-beta`；`release.yml` 的 bump 用**值**做 sed 匹配（找 `__version__ = "0.5.3-beta"`），在该文件里 **0 匹配** → `__init__.py` 永不被 bump → **发出去的包对自己的版本撒谎**（`import zoo_framework; __version__` 得到 `0.1.1-beta`）。本任务只改**这一个字面值**使其与另两处一致；`release.yml` 那条 sed 改为匹配**键**（与值无关、不再静默 no-op）归**并行会话**，本变更不碰该文件。**已完成**：三处现均为 `0.5.3-beta` ✓（实测逐处比对：`pyproject.toml` / `.env` / `zoo_framework/__init__.py`）

## 8. 收尾验证

- [ ] 8.1 端到端验证门禁有效性：临时引入一个类型错误 → 本地类型检查失败且退出码非零 → 撤销后通过且退出码为零；验证：两次结果符合预期，且第二次的通过是**真实的零错误**而非被 `ignore` 压制
- [ ] 8.2 全量回归确认未破坏运行时行为；验证：`pytest -q` 全绿，用例总数不少于 `fix-runtime-defects` 完成后的数量
- [ ] 8.3 确认未夹带范围外改动；验证：`git diff --stat` 限于 `pyproject.toml`、`.gitignore`、`.pre-commit-config.yaml`、`.github/workflows/`、`uv.lock`、`example/`、仓库根 `__init__.py`、`zoo_framework/__init__.py`（7.6）及为消除类型错误所必需的最小源文件调整，不含新增运行时依赖

---

## 重取基线结论（本节的元记录）

重取基线时发现**原始任务表把若干前提写成了已完成或未变**，实测不符：1.1 的两条断言一条部分为假、一条不成立；6.2 的理由（"当前必失败"）因 Pages 启用与 `mkdocs.yml` 落地而过期；6.3 只完成了一半却被记为整条；6.1/7.3/7.4/7.5 确已完成但表中未标；分类"第三方存根缺失"**按配置恒为空**；另有两条**本变更自己造成的耦合**原表不可能有（4.6 的本地钩子、7.6 的版本值）。

**这是同一族问题的又一次实例**：把"我以为的状态"写成断言，而它与事实不符。本仓库这一轮已因此改过三份规范（全称断言为假、载体枚举不全、MODIFIED 漏带 Scenario）。故本表的处理方式沿用同一取向——**不靠记得更新，靠每次执行前重新取事实**：1.2 的存在意义就是每轮重取基线，而**这次重取恰好证明了它必要**。

**一处刻意的克制**：本表**不**给出"已完成/未完成"的总计数（如"5/31 已完成"）。计数是手维护事实，本仓库已实测它会漂移（任务书估"六处"载体、实得七处）。状态以每个条目前的标记为准，读者可按标记现数。
