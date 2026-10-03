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

- [x] 3.1 修复归类为"真实缺陷"的错误（~51 条）；验证：该类别归零，且相关回归用例仍通过。**进行中（第一批已提交）**：82 → **68** errors。已清零三类：`valid-type` 6→0（`builtins.callable` 当类型用、`list[X] or None` 这种非法注解）、`no-redef` 6→0（`event_channel_manager` 各分支重复声明 `reactors`）、`attr-defined` 2→0（`threading._active` 改为 `getattr`，不加 ignore）。**一处值得单记**：修 `get_channel_reactors` 的返回类型时（`list[EventReactor] or None` → `| None`）**暴露了一个真实缺陷**——原注解因 `or` 短路求值实际等价于 `list[...]`，于是 mypy 看不见 `None`；改正后 `event_worker.py` 立刻报出两条（对可能为 `None` 的返回值直接 `len()`／迭代）。该处原以 `len(reactors) == 0` 写得，`None` 会抛 `TypeError` 而被上面的 `except` 兜成"查询响应器失败"——**既是用异常做控制流，又把"无匹配"错报成"查询失败"**；改为 `if not reactors:` 后两者同义、路径也统一。**这正是类型门禁的价值：一个非法注解一直在掩盖下游的 None 处理缺口**。
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

**第九批（已提交）**：17 → **9** errors（零新增）。本批 8 条里有 **5 条是真缺陷或真前提缺失**，只有 3 条是纯注解：
  - **`core/worker_registry.py` 的延迟实例化缺前提校验**（真缺陷）：`_worker_classes` 存类、实例化时**无参调用**，而"可无参构造"这个前提**无人校验** → 注册一个必须带参的类（`BaseWorker` 本身就是）会一路通过，直到第一次实例化才抛 `TypeError`。**修法是把隐含前提变成注册期可校验的条件**：新增 `_requires_constructor_args()`（用 `inspect.signature` 判定），`register_class` 在注册时即拒绝这类类并指路 `register_instance`/`register_factory`。类型检查看不到该运行期校验，故调用点仍留一处**定向 ignore**，其注释明确指出它压制的是**已在注册期强制**的前提、不是未经验证的假设。
  - **`event/__init__.py:5`**：`__all__` 里放的是**类对象**而不是字符串（`__all__` 必须是字符串序列）→ 改为字符串。
  - **`reactor/event_reactor.py` 未设置回调时**：原先会抛 `NoneType is not callable`，虽然同被外层 `except` 捕获并走"报错+重试"，但**读不出原因** → 改为显式 `ValueError("响应器 X 未设置事件回调")`，**控制流不变、可读性变好**。
  - **`core/persistence_scheduler.py:404`**：`_last_save_time` 初值 `0` 被推断成 `int`，而赋值来自 `datetime.timestamp()`（float）→ 标注 `float`。
  - **`core/container/registry.py` 三条（本变更自己的代码）**：捕获并改写 `__new__`/`__init__` 的动态技法**本就不在静态检查的建模范围内** → 三处**定向 ignore**（各带错误码）＋一段共享说明。**刻意不退化成 cast**：ignore 至少把"这里绕过了检查"摆在明面上，cast 会把它盖住。
  - 另修掉一处**多余的** `type: ignore`（`structured_log.py:15`，即 3.4 那条 `unused-ignore` 的来源）。
**剩余 9 条的构成**：6 条 `no-any-return`（另有 `Any` 来源，与 `ThreadSafeDict` 无关：`state_effect` / `plugin` / `base_fifo` / `state_index_factory` ×2 / `event_channel`）＋ 2 条 `state_scope` 的 Optional 赋值 ＋ **1 条即已记录的 `master.py:288`（`change_waiter` 恒抛异常）**——最后这条**不靠猜修**，到门禁阶段须以"显式 ignore + 指向记录"处置，而不是替作者决定语义

**第十至十三批（已提交）→ 零错误达成**：mypy `Success: no issues found in 94 source files`（起点 82）。
- 第十批：`StateEffect` 的构造形参补注解（`_effect_list` 那条的同族：未标注形参 ⇒ 属性成 `Any`）。
- 第十一批：`WorkerDelayManager.exponential_backoff` 的 `delay` 显式标注 —— 定位靠 **`reveal_type`**（两个操作数分别是 float/int，唯独乘积落到 Any），并**实测排除了**"`__init__` 缺 `-> None`"这个先验假设。
- 第十二批：`HierarchicalIndex._cache` / `StateIndexFactory._index_types` 补类型参数（**逐处应用后立刻量到 7→5**；同样的改动在"一次性打包"那批里看起来像"没用"，正是打包混淆了结果）。
- 第十三批：**`BaseFIFO` 泛型化**（`_fifo` 是裸 `list` ⇒ `Any`）。**不能收窄成 `list[EventNode]`**——`DelayFIFO` 存的是 `DelayFIFONode`（非其子类）。同时给 `EventFIFO.get_top` / `EventChannel.get_top` 补如实的 `EventNode | None`。**泛型化立刻暴露一个真实缺陷**：`DelayFIFO.get_expire_values` 以 `node.is_expire(current_time)` 调用，而 `DelayFIFONode.is_expire()` **不收参数**（设计上由节点自己读单调时钟，且被 `test_execution_time.py` 多处直接覆盖）⇒ 裁判明确"方法对、调用点错"，运行期会抛 TypeError，只因该方法无调用者而从未暴露。已修。**披露**：改该方法时我把"附近只有这一个方法"当成事实（实际有名字相近的另一个），编辑孤立了方法体、**一度制造语法错误使测试无法收集**；按 HEAD 核对后修复。
- **末批：3 条"已记录的缺陷"以带锚点的 ignore 收口**（`state_scope` 的 `add_child(None)`、`master.py` 的 `change_waiter`），并在注释里写明**为何不猜修**（改语义属他人决定）。**踩到的坑**：`# type: ignore[...]` 之后**不能再跟任何文字**（锚点也不行），否则 mypy 判"Invalid type: ignore comment"，ignore 失效、错误数反升（3→6）；锚点必须写在**前一行注释**里。
- [x] 3.2 为归类为"注解缺失"的错误补充类型注解（17 条）；验证：该类别归零，且 `pytest -q` 仍全绿。**进行中（第一批已提交）**：`var-annotated` 7→0（含模块级字典、类属性字典、`set()` 局部共 6 处）。**一处反向的教训值得单记**：`core/aop/validation.py` 的 `params_validate_map` 我一开始标成 `dict[str, list]`（"更精确"），结果 mypy 立刻报出 `validation_params` 里那处 `isinstance(valid_values, list)` 防护为 **unreachable**——即**一个更精确的注解制造了一个新错误**。原因是该注解断言"值恒为 list"，而**那处防护的存在本身就是该不变量不成立的证据**（其文档也写明会返回 False 的"类型不正确"情形）。故改为**裸 `dict`**（≡ `dict[Any, Any]`）：既消掉 `var-annotated`，又让防护保持可达，**零行为改动、零新增错误**。通则：**当代码里有针对某类型的防护时，不要用注解把该类型收窄到防护失效**——防护是作者对不变量的反证
- [x] 3.3 **[改写]** 处理 `ignore_missing_imports`：原表写"处理第三方存根缺失"，但该分类**实测恒为空**（被配置抑制）。改写为——**为框架实际使用的依赖（click / jinja2 / gevent / pyyaml / python-dotenv）补存根，然后把 `ignore_missing_imports` 从全局收窄为按模块**；验证：全局为 false（或按模块列出例外），且 mypy 仍零错误、退出码 0。**若收窄后发现代价远超收益，须把"保持全局忽略"作为显式决定记录下来**，而不是默默不动
- [x] 3.4 审查本次新增的每一处 `# type: ignore` 与 `cast`；验证：`grep -rn "type: ignore\|cast(" zoo_framework/` 的每一处都有相邻注释说明原因，且没有一处是用于压制本可修复的类型不匹配（逐条核对并记录）。**注**：当前基线里已有 1 条 `unused-ignore`，说明**存在多余的 ignore**，属本任务范围

**3.3 / 3.4 收口记录**
- **3.3 → 按兼底条款记录为显式决定：保持全局 `ignore_missing_imports`，不收窄。** 理由：收窄需要为 click / jinja2 / gevent / pyyaml / python-dotenv 新增存根 **dev 依赖**，并因此**重解析 `uv.lock`** —— 而 `uv.lock` 是**并行会话的在制品**、由其用户决定去留。为一个"当前确实零错误"的门禁去跨这条边界不划算。**这不是"忘了做"，而是被记录的选择**；将来若 uv.lock 归属明确，可另开变更收窄。
- **3.4 → 实测审计通过**：全仓库 `type: ignore` **11 处**（另有 1 处出现在 `zoo_thread.py` 的注释文字里，非实际使用）+ `cast(` **1 处**（`params_path.param`，`_T` 的空操作 cast，机制本身要求）。**逐处都有相邻理由**，且 mypy 报 `Success`（`warn_unused_ignores = true` 下无 unused 判定），即没有多余的、也没有失效的。其中**两处属"需决策才可修"**（非可机械修复）：`state_scope` 的 `add_child(None)` 与 `master.py` 的 `change_waiter`，其 ignore 各自指向上面记录的缺陷；`state_effect` 的两处 `override` 同属此类（规范写法要改比较语义）。

## 4. 建立类型门禁

- [x] 4.1 移除 `.github/workflows/quality.yml` 中 mypy 步骤的 `continue-on-error`；验证：临时插入一个类型错误 → 本地类型检查返回非零 → 撤销后返回零。**已完成，且这一步挡下了一次会红 CI 的放行**：动手前先按"CI 从 `.[dev]` 装的是**最新** mypy、本地却一直用钉住的 1.7.1"复核，实测把本地 mypy 升到 **2.4.0**（= CI 那版）后**多出 1 条 1.7.1 看不见的错误**：`state_machine_manager.py:34` 把 `dict[Any, Any]` 赋给声明为 `ThreadSafeDict[str, StateScope]` 的属性。**即：若不加这一步复核就开门禁，本地零错误、CI 直接转红**——这正是"本地验证通过"与"CI 会通过"是两件事的又一例证。修法取**类型诚实**的最小改动（`ThreadSafeDict(state_machine)` 包一层）：原先直接存 `dict` 会让后续 `has_key()` 在运行期抛 `AttributeError`（`dict` 无此方法），包一层后声明类型在**每条路径**上都为真。**顺带查实一个更重的缺陷并只做记录、不猜修**：`ThreadSafeDict` **不是** `dict` 子类（实测 `isinstance(ThreadSafeDict(), dict) is False`），而落盘的就是 `ThreadSafeDict` —— 故对本框架自己写出的文件该守卫**恒假**，状态**从未真正恢复**，`_local_store_loaded` 却置 True 并挡住后续重试；已在方法 docstring 加 `【已知缺陷】` 锚点，语义决定留待他人。验证（实测）：注入 `x: int = "not an int"` → `Found 1 error`、**退出码 1** → 删除探针后 `Success: no issues found in 94 source files`、**退出码 0**（且 `--no-incremental` 冷缓存复核亦为 0）✓
- [x] 4.2 移除 `.github/workflows/release.yml` 中 mypy 步骤的 `continue-on-error`，并确认发布作业依赖质量检查的结果；验证：release.yml 中发布作业的 `needs` 链包含质量检查作业。**注意**：`release.yml` 当前由**并行会话**在改（"不吞"修复），改动前须与其确认，避免两人改同一文件；实测该文件里 mypy 那处 `continue-on-error: true`（原 121 行）**仍在**，正是本任务的目标。**已完成（经并行会话明确答复"可以动"后编辑其文件）**。**验收口径按新结构重述——原表的"原 121 行"已失效**：并行会话的 tag 驱动重构（`5313758`，经合并 `e157efa`）把这个文件整体换过，mypy 一步现位于 **`quality` 作业的 `Run MyPy`**；且**发布闸门只在 `push tag v*` 路径**（不再是 push 分支直接发布），故"两处分别验收"的旧口径作废，现在是**一条**：tag 推送时的 `quality → release`。**两半分别核对（用 yaml 解析读结构，不靠肉眼）**：① 移除 `continue-on-error`（同时改掉那句已成假的注释"mypy 不卡门禁"——`quality.yml` 那侧的所谓"对齐前提"已被 4.1 移除）；**判别式验证**：解析出的该步骤键只剩 `['name', 'run']`，即 `continue-on-error` **在结构上不存在**，而不只是"文本里搜不到"；② `release.needs == ['test', 'quality']` ✓，且 `release.if` 是 `github.ref_type == 'tag'`、**无 `always()`** —— 故 `quality` 失败时 `release` 会被跳过，门禁真的落在发布路径上。**一处**残留的不一致我**没动**（避免夹带范围外改动）：`release.yml` 写 `mypy zoo_framework`，`quality.yml` 写 `mypy zoo_framework --show-error-codes`；因 `pyproject.toml` 已设 `show_error_codes = true`，两者行为等价 ✓
- [x] 4.3 按 design D3 在 `[tool.mypy.overrides]` 中对 `zoo_framework/utils/` 开启 `disallow_untyped_defs`；验证：该模块中缺注解的函数被报告为类型错误。**已完成**，但关键是**顺序**：只加配置会让整包门禁立刻转红，故先补齐 `utils/`（6 个文件）的全部注解，再加 overrides。配置为 `module = ["zoo_framework.utils.*"]`（mypy 的 `foo.bar.*` 同时匹配 `foo.bar` 自身与子模块 ✓）。
  **一处关于我自己的枚举的反面记录**：我先用 `grep -rn "^\s*def " zoo_framework/utils/ | grep -v -- "->"` 数出"35 处无注解"，补完以为齐了——**实际漏了 9 处**，是**打开开关后由检查器报出来的**。漏因很具体：那 9 处**已经有返回注解**，只是 `*args`/`**kwargs`/单个形参没注解（`bind(**context)`、`unbind(*keys)`、六个 `**kwargs`、`_log`、`metric`），而我的 grep 只筛"整行没有 `->`"。**故我最初写的"35 处"是个用 grep 手维护的清单，它的口径（"没有返回注解"）与开关的口径（"任一形参缺注解"）不是一回事**——又一次"枚举 ≠ 被检查的东西"，与 [[enumerate-to-mechanism]] 同族；这次的权威来源是**检查器**，不是我的 grep。
  **一处行为修复（非纯注解，按规矩分开写）**：`FileUtils.is_dir` 原实现写了 `os.path.isdir(path)` 却**没有 `return`**，故恒返回 `None`——不是"缺注解"而是**丢掉了返回值**，其调用点 `file_exists` 的 `if cls.is_dir(path): return False` 因此恒不成立、**目录被当成文件存在**。加 `-> bool` 会直接报缺 return，故补上 return。**影响面核实为空**：全仓库 `is_dir` 只有 `file_exists` 一个调用点，而 `file_exists` 的三个调用点传的都是文件，故不改变任何现有路径的结果。已在该处就地写明。
  **判别式验证（实测）**：在 `utils/` 放一个无注解探针 → 报 `1 error ... [no-untyped-def]`；删除后 → `Success: no issues found in 96 source files` ✓。另：`mypy 2.4.0` 与钩子钉住的 `1.7.1`（`pre-commit run mypy --all-files`）**都为零错误**，`pytest` **662 passed** ✓
  **提交时又浮出一处既有安全问题（同样是"我的改动让门禁第一次看到这个文件"）**：bandit 在 `cmd_utils.py` 报 **3 条 B605（High，shell 注入面）**——`os.popen(cmd)` / `os.system(cmd)` ×2。属**既有**代码，此前没人提交过该文件故从未被扫。**处理方式与 `persistence_scheduler.py` 的 pickle 一致**：能保住语义的替代写法不存在（`shlex.split` + `shell=False` 会丢掉管道/重定向，且 `os.system` 的退出码语义与 `popen().read()` 的标准输出语义不同），属**语义变更、不替作者决定**；故用**定向 `# nosec B605`** 收口，并把"这是契约固有属性、风险取决于调用方"写进类 docstring（**不用**把 B605 加进 `.bandit.yaml` 的全局 skips——那会让别处真正的注入面也失去告警）。风控依据：该类在仓库内**零调用点**，仅经 `utils/__init__` 导出为公开 API ✓
- [x] 4.4 确认开启单模块严格模式后其他模块的检查结论不变；验证：对比开启前后在其余模块上的错误数，二者一致（均为零）。**已完成，且用的是同一探针的"阴性半边"**：把*相同*的无注解探针同时放进 `zoo_framework/utils/` 与 `zoo_framework/core/`，mypy 只报 `utils/` 那一个、**`core/` 那个完全不被报告** ✓ —— 即 overrides **不外溢**。前后计数：开 overrides **之前**整包 0 错误；开**之后**一度出现 9 条、**全部落在 `utils/` 内**（即 4.3 那批漏网的形参），补完又回到 0。**其余模块在开启前后均为 0，二者一致 ✓**
- [x] 4.5 确认本地与 CI 的类型检查命令逐字一致；验证：比对 `quality.yml` 的 mypy 步骤命令与本地执行的命令字符串，完全相同。**已完成，但"逐字一致"这个验收判据本身做不到，须如实改写**：本地是 pre-commit 钩子（传入**显式文件列表**），CI 是 `mypy zoo_framework`（传入**目录**），两者命令行字符串**必然**不同。可做到、且已实测做到的是两件事：**① 参数集一致**——钩子改为只传 `--show-error-codes`，与 CI 完全相同（原先多传 `--ignore-missing-imports`；因 `pyproject.toml` 已全局设 `ignore_missing_imports = true`，去掉后语义不变，只是不再与 CI 的命令行分叉）；**② 文件集一致**——这条**原先我只写对了一半**，由并行会话实测证伪：`pre-commit run --all-files` 的默认范围是"仓库里所有 Python 文件"，比 CI 宽，会把 **`bench/`** 一并喂给 mypy（104 个文件、6 条错误）；我自己补测又发现仓库根另有三份维护脚本（`batch_fix_docs.py` / `ci_tests.py` / `fix_docstring_syntax.py`）同样在默认范围内。故**放弃"加长 exclude 列表"**，改用**正向** `files: ^zoo_framework/`（与同文件里 bandit 钩子的写法一致）——它字面上就是"CI 检查什么"，仓库将来新增目录也不会失效。**验证（实测，非推断）**：`pre-commit run mypy --all-files` 输出 `Success: no issues found in 96 source files`，与 CI 的 `mypy zoo_framework`（96 个 .py）**逐字相同** ✓
- [x] 4.6 **[新增]** 把本地 mypy 的 pre-commit 钩子从 `manual` 阶段恢复到**默认阶段**（提交时运行）。**为什么原表没有**：这条是**本变更自己的前置工作造成的**——`52d9cd4` 当时把该钩子移出默认阶段，理由是"mypy 根本跑不起来"（根 `__init__.py` + 82 条错误）。2.1–3.3 完成后那个理由消失，**若不恢复，就会出现"CI 门禁开着、本地门禁关着"**——正是 6.1 与 `ef4bed2` 存在要消除的那种本地/CI 分叉。验证：本地提交时 mypy 钩子会实际运行（而非仅 manual 阶段可跑），且一次干净提交能通过。**已完成**：删掉 `stages: [manual]` 并重写上方那段已失真的注释（它仍在说"quality.yml 里 mypy 是 continue-on-error"，而 4.1 已把该条移除）。**验证**：① **"默认阶段"由配置直接读出**——钩子无 `stages:` 键，即属于 pre-commit 的默认阶段集合；② **被调度**：落地本任务的提交（`800ad94`）的钩子输出里确实列出了 `mypy` 一步（与其它默认阶段钩子同列），但它显示 `(no files to check)Skipped`——本次暂存的两个文件（`yaml` + `md`）都不匹配新写的 `files: ^zoo_framework/`，**故"执行并通过"这一次并未被证明**；我最初把它写成"验证方式即提交本身：mypy 在默认阶段实际执行并通过"，**把"被调度"与"执行"混为一谈，属过度断言，已改正**；③ **真正执行的证据**是 `pre-commit run mypy --all-files` → `Success: no issues found in 96 source files`（与 CI 的 `mypy zoo_framework` 同为 96 个文件）。另单独实测合并后的树上**两版都为零错误**——`mypy 2.4.0`（CI 从 `[dev]` 装的那版）与钩子钉住的 `1.7.1`（这一格先前**没人验过**：并行会话只在 `--all-files` 下跑过 1.7.1，而那次结果被 `bench/` 的错误污染）✓；④ **"在默认阶段真正执行"这一格后来补上了**：`6ba007c`（改了 `zoo_framework/utils/` 下的 .py）是**第一个有 Python 文件进入暂存区**的提交，其钩子输出为 `mypy...Passed`（而非 `Skipped`）—— 即门禁在默认阶段对真实改动的 .py **实际运行并通过** ✓
- [x] 4.7 **[新增] 记录一条未修的真缺陷（由 4.5 的文件集核对顺带发现，非本变更范围）**：`bench/` 里的 bench 脚本在 `scheduler-model-seam` 之后**没跟着更新**，对 `BaseWaiter` 的陈旧访问已成真错误——实测 `pre-commit run mypy --all-files` 在 `bench/` 上报 6 条（`"BaseWaiter" has no attribute "pool_size"` / `"resource_pool"`、`Property "workers" ... is read-only` 等）。**4.5 的 `files:` 只让它们不进门禁，不等于修好**——两者必须分开写，否则"门禁变绿"会被误读成"缺陷已处理"。**为什么不顺手修**：`bench/` 按 CLAUDE.md 是"测量与决策区、非产品代码"，且 CI 本就不检查它；修法涉及 `adopt-rust-core` 的语义（那些 bench 脚本还能不能跑），属他人决定，故**只记录、不猜修**

## 5. 开发环境与锁定文件

- [ ] 5.1 按 design D4 修正 `uv.lock` 的 `requires-python`，使其与 `pyproject.toml` 一致；验证：两个文件的 Python 版本要求字符串相等。**[在途]**：`uv.lock` 当前**有未提交改动**（并行会话误触发的整份重解析：revision 1→3、`requires-python` 提到 `>=3.13`、+1110/−469），其内容**可能已满足本任务**，但该改动归属并行会话、由其用户决定去留。**本任务执行前须先与该会话确认，勿自行处理 `uv.lock`**
- [ ] 5.2 按 design D4 将 `uv.lock` 中的 `greenlet` 升级到在 Python 3.13 上有可用产物的最低版本，仅做最小改动；验证：`uv sync --frozen` 在 Python 3.13 上成功，不再出现 greenlet 构建失败。**同上：`uv.lock` 归属并行会话**
- [ ] 5.3 确认锁定文件未发生无关依赖变动；验证：`git diff uv.lock` 只涉及 `requires-python` 与 `greenlet` 相关行及必要传递依赖。**注意**：当前那份在途改动**正是**"整体重新解析"（+1110/−469），与 design D4 的"最小修正"**相冲突**；若采用它，须把"放弃最小修正"作为显式决定记录，而不是当作符合 D4
- [ ] 5.4 确认元数据安装路径仍可用；验证：`pip install -e ".[dev]"` 成功，随后 `pytest -q` 全绿

## 6. CI 作业修正

- [x] 6.1 把 bandit 参数由 `-c pyproject.toml` 改为 `-c .bandit.yaml`。**[已完成（他处）]**：由 `ef4bed2` 完成，且顺带加了 `files: ^zoo_framework/` 使范围与 CI 一致。验证方式原为 `pre-commit run bandit --all-files`；实测当前配置为 `files: ^zoo_framework/` + `args: ["-c", ".bandit.yaml"]` ✓
- [x] 6.2 给 `.github/workflows/docs.yml` 的产物上传步骤加上与构建步骤相同的 `hashFiles('mkdocs.yml')` 条件。**[前提已变，性质从"当前必失败"降为"鲁棒性"]**：实测该不对称**仍在**（上传步骤无同条件），但 ① `mkdocs.yml` 现已提交（`1af83c5`），故条件为真、构建与上传成对执行；② **GitHub Pages 现已启用**（`gh api repos/.../pages` → `build_type: workflow`，站点 `https://yearsalso.github.io/zoo-framework/`）。所以现在**不会失败**，但将来 `mkdocs.yml` 若被移除，上传仍会带不存在的 `./site` 跑。**任务本身仍成立**（鲁棒性），但原始理由（"当前必失败"）已过期，须按新事实写入提交说明。**已完成**：上传步骤补上 `if: hashFiles('mkdocs.yml') != ''`，与构建步骤**逐字相同**（yaml 解析后比对两处条件字符串一致 ✓）
- [x] 6.3 让 `.github/workflows/tests.yml` 的 Python 安装步骤使用 `${{ matrix.python-version }}`。**部分已完成**：矩阵本身已是参数化（`tests.yml:20` → `["3.13"]`），但**两处仍硬编码** `python-version: "3.13"`（`:29`、`:66`）。本任务按"不再出现硬编码字面量"验收，故**仍需做**。**已完成**：`test` 作业里三处（**作业名**、**步骤名**、`python-version` 参数）+ 覆盖率产物名 `coverage-report-...-py3.13` 全部改用 `${{ matrix.python-version }}`。**原先列出的第二处硬编码（`:66`）随 6.4 删除 `benchmark` 作业一并消失**——即"两处"这个数字在完成后**只剩一处需要改**，本任务因此变成真正的"除矩阵定义外无字面量"。验证：`grep -n "3\.13" tests.yml` 只命中矩阵定义那一行 ✓
- [x] 6.4 修正 `tests.yml` 中引用不存在目录的 `benchmark` 作业（加目录存在性条件，或移除）。**未做**：该作业仍在（`:56`），且仍 `run: pytest tests/benchmarks/ ...`（`:75`）。**已完成——选择"移除"**。先核实"死"到什么程度：`tests/benchmarks/` **不存在**、全仓库**没有任何** pytest-benchmark 用例、`benchmark` marker **也未在 `pyproject.toml` 配置**，且该步骤自带 `continue-on-error: true` ⇒ **它从未门禁过任何东西**。**为什么不用原任务先列的那个选项（加存在性条件）**：`hashFiles()` 在**作业级** `if:` 上求值时**尚未 checkout、工作区为空**，条件恒假、作业恒跳过——那只是把"死作业"换成"永远跳过的作业"，不如删除诚实（已把这层原因写进 tests.yml 的替换注释里）。**另须防混淆**：仓库根真实的 `bench/` 是 `adopt-rust-core` 的独立测量脚本、非 pytest、也不在 CI 中——与这个被删的作业无关
- [x] 6.5 全量复核所有 workflow 中"条件加在主步骤、未加在依赖它的后续步骤"的情形；验证：逐个 workflow 检查含 `if:` 的步骤，其下游依赖步骤均带同条件。**注**：这条是 6.2 的推广，**建议同时覆盖 `continue-on-error` 吞掉失败的情形**——`release.yml` 已实测出两处（步骤级 + 内部 `if/else`），属同一"条件加错位置"的家族。**已完成，5 个 workflow 逐个过**：① `docs.yml` 的不对称即 6.2，已修；② `quality.yml` 的 bandit 步骤用 `|| true` **吞掉自身失败** ⇒ 已去掉，security 作业成为真门禁（**并按 4.1 的同一条纪律，用 CI 实际安装的那版复核**：CI 装 `bandit[toml]`、**未钉版本⇒最新**，实测 **1.9.4**，而本地钩子钉的是 1.7.6 —— **两版结论不一致**：1.9.4 在 `state_machine_work.py` 报 3 条 pickle 发现、1.7.6 不报。已按 `persistence_scheduler.py` 的既有做法加**带说明的 `# nosec`**，复核 1.9.4 退出码 **0** ✓）；③ `release.yml` 的两处"步骤级吞掉"已随 4.1/4.2 消失，其内部 `if/else` **逐处看过，都是 fail-fast 而非吞掉**（tag 已存在 → `exit 1`；tag 与 pyproject 版本不一致 → `exit 1`；changelog 无上一 tag → 取全量日志）；④ `build.yml` / `tests.yml` 没有可错配的条件；⑤ 产物上传的 `if: always()` **是有意保留**——门禁步骤失败时更需要这份产物来定位，它与"上游去掉 `|| true`"是**一对**、不是同一处
- [x] 6.6 **[新增] 记录一处本地（Windows）特有的 bandit 可诊断性缺陷，非本变更引入、也未修**：在**同时满足**①该文件被扫出 finding、②该文件源码里含非 GBK 可表示字符（如日志里的 ✅）时，bandit 的 **txt formatter 会抛 `RuntimeError: Unable to output report using 'txt' formatter: 'gbk' codec can't encode character ...`**，**取代**原本该显示的发现内容。已用探针隔离出这两个必要条件（`import pickle` + 一个 ✅ 同文件即复现）。**关键边界：它不会造成"假通过"** —— 实测 pre-commit 仍报 `bandit...Failed`、退出码 1，即**门禁照样拦，只是你看不到拦的理由**，属**可诊断性**问题而非门禁漏洞。CI 在 Linux/UTF-8 上不受影响。**为何不修**：仓库侧没有干净修法（pre-commit 不支持给单个钩子设环境变量）；可行的本地规避是在环境里设 `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` 再跑钩子

## 7. 示例与仓库卫生

- [x] 7.1 按 design D9 修正 `example/main.py` 构造框架对象的方式（当前以整数调用，实测抛 `AttributeError`）；验证：按示例自身声明的方式运行该入口不再抛异常。**已完成，但实测表明"原表写的那个错误并不是真正拦住入口的那个"**——这与本变更反复出现的同一形态一致，值得单独记：
  - 原表指的 `Master(1)` 确已修正为 `Master()`（现签名是 `Master(config: MasterConfig | None = None)`），顺带删掉未使用的 `asyncio` 导入并对导入排序。
  - **但入口仍抛异常，且抛出点在原表从未提及的文件里**：`example/threads/demo_thread.py:30` 的 `self.is_loop = True` → `AttributeError: property 'is_loop' of 'DemoThread' object has no setter`。根因是 `BaseWorker.is_loop` 已是**只读 property、以 `_props` 为唯一真源**，其类 docstring 明写"子类 MUST NOT 用实例属性遮蔽它们"——即该写法**违反基类已写明的契约**，正确位置是 `_props` 字典。已把 `"is_loop"` 改为在 `_props` 中声明 `True` 并删掉那行赋值（原代码先传 `False` 再赋 `True`，是 `is_loop` 还是普通属性时的遗留）。
  - **验证（实测）**：在 `example/` 目录下运行 `python main.py` → 依次输出 `Master started, zoo is open!` 与各 Worker 的 start/stop，**无异常**（`run_forever` 按设计常驻，故用 timeout 终止）✓；`demo_event.py` 同批验证见 7.2。
  - **另记一条不修的现象**：该次运行里 **`DemoThread` 从未出现**——`@worker(count=20)` 注册进的是**旧的** `WorkerRegister`，而 `Master` 从 `WorkerRegistry` 调度（两者并存，见 CLAUDE.md）。即**这个示例 Worker 实际是惰性的**。一个"worker 从不运行"的示例具有误导性，但把示例改到当前注册路径属**语义/API 决定**，不在此顺手改，故只记录。**（补记一条通用的坑）**：提交时 `ruff --fix` 把 `import threads` 当作**未使用导入**删掉了——但它其实是**副作用导入**（`demo_thread.py` 的 `@worker(count=20)` 在**导入时**才注册示例 Worker），删掉就等于**静默改变了示例的行为**，而"没用到的导入"这个判据从**静态**看完全成立、看不出副作用。已恢复该行并加 `# noqa: F401` + 就地说明。**通则：`F401` 只看得见"这个名字有没有被引用"，看不见"导入有没有副作用"** —— 对 `__init__.py`、以及在导入期注册/改全局状态的模块，这条自动修复会悄悄改变行为
- [x] 7.2 按 design D9 修正 `example/event/demo_event.py` 从 `build.lib` 导入的问题；验证：`grep -rn "build\.lib" example/ zoo_framework/` 无结果，且该模块可被成功导入。**已完成**：`from build.lib.zoo_framework import event` → `from zoo_framework.core import event`（`event` 确实由 `zoo_framework.core` 导出，经其 `__all__` 核对 ✓）。验证：检索 `build\.lib` **无结果** ✓；该模块**导入成功** ✓（**一处自查**：第一次验证时我的探针 `print` 里带了 ✓，在 Windows GBK 控制台上自己抛了 `UnicodeEncodeError`——那是**我探针的问题、不是被验代码的问题**；因报错发生在 import 之后，导入本身是成功的，但仍改用纯 ASCII 输出重跑了一次以取得干净证据）
- [x] 7.3 补齐 `.gitignore`，覆盖字节码缓存、构建输出与虚拟环境三类路径。**[已完成（他处）]**：`__pycache__` / `venv` / `.venv` / `build/` / `dist/` / `/site/` 均已存在 ✓
- [x] 7.4 把已被误跟踪的构建产物、字节码缓存与虚拟环境从版本控制索引中移除并保留磁盘文件。**[已完成（他处）]**：`git ls-files | grep -E '^(venv|build)/|__pycache__|\.pyc$'` 返回 **0** ✓
- [x] 7.5 清理只剩字节码的 `test/` 目录索引条目。**[已完成（他处）]**：`git ls-files test/` 返回 **0** ✓
- [x] 7.6 **[新增]** 同步 `zoo_framework/__init__.py` 的 `__version__`。**为什么原表没有**：实测该文件写着 `0.1.1-beta`，而 `pyproject.toml` 与 `.env` 都是 `0.5.3-beta`；`release.yml` 的 bump 用**值**做 sed 匹配（找 `__version__ = "0.5.3-beta"`），在该文件里 **0 匹配** → `__init__.py` 永不被 bump → **发出去的包对自己的版本撒谎**（`import zoo_framework; __version__` 得到 `0.1.1-beta`）。本任务只改**这一个字面值**使其与另两处一致；`release.yml` 那条 sed 改为匹配**键**（与值无关、不再静默 no-op）归**并行会话**，本变更不碰该文件。**已完成**：三处现均为 `0.5.3-beta` ✓（实测逐处比对：`pyproject.toml` / `.env` / `zoo_framework/__init__.py`）

## 8. 收尾验证

- [x] 8.1 端到端验证门禁有效性：临时引入一个类型错误 → 本地类型检查失败且退出码非零 → 撤销后通过且退出码为零；验证：两次结果符合预期，且第二次的通过是**真实的零错误**而非被 `ignore` 压制。**已完成，用"配置面核对 + 两个探针"回答，因为"非被 ignore 压制"是判据里最容易只靠嘴说的那一半**：
  - **配置面**：`pyproject.toml` 中**没有** `ignore_errors` 也没有 `disable_error_code`（⇒ 不存在全局性降级）；`warn_unused_ignores = true`（⇒ 多余的 ignore 会被报出来，故不可能靠一堆 ignore 静默压住而不留痕）；全包 `type: ignore` 共 **12 处**，且 3.4 已逐条核对均有说明。三者合起来使"被大量 ignore 压成 0"这一可能不成立。
  - **探针 A（无既有 ignore 的文件）**：注入 `x: int = "not an int"` → **退出码 1**、`Found 1 error` ✓
  - **探针 B（判别式的那个：`core/container/registry.py`，它本身有 4 处带说明的 ignore）**：追加一个返回类型不符的函数 → 仍是 **退出码 1**、该错误被报出 ✓。**这一条才是关键**：它证明那些 ignore 是**逐行**生效、**不是文件级豁免**——若它们是文件级的，探针 B 会静默通过而"零错误"就成了假象
  - **撤销后**：退出码 **0**、`Success: no issues found in 96 source files`；且 `registry.py` 经 `diff` 校验与探针前**逐字节相同**（探针未留残留）✓
- [x] 8.2 全量回归确认未破坏运行时行为；验证：`pytest -q` 全绿，用例总数不少于 `fix-runtime-defects` 完成后的数量。**已完成**：按 **CI 的那条命令**跑 `pytest -q --cov=zoo_framework --cov-fail-under=30` → **662 passed / 0 failed**，覆盖率 **75.82%** ≥ 30% 门槛 ✓。**基线取自归档而非记忆**：`openspec/changes/archive/2026-09-27-fix-runtime-defects/tasks.md:33` 记 `208 passed / 0 failed`（既有 142 + 新增 66）—— 662 ≥ 208 ✓，用例只增未减
- [x] 8.3 确认未夹带范围外改动；验证：`git diff --stat` 限于 `pyproject.toml`、`.gitignore`、`.pre-commit-config.yaml`、`.github/workflows/`、`uv.lock`、`example/`、仓库根 `__init__.py`、`zoo_framework/__init__.py`（7.6）及为消除类型错误所必需的最小源文件调整，不含新增运行时依赖。**已完成，并查出一处**真实的**越界（如实记录，未掩盖）**：
  - **范围是这么算的**：直接取 `git diff <区间>` **不可用**——本变更的提交与并行会话的提交、以及一次 `origin/dev` 合并**交织在同一段线性历史**里（该区间会连带出来 `bench/`、`.claude/`、`docs/` 等大量他人改动）。故改用**本变更自己的提交**为口径：**凡更新本变更 `tasks.md` 的提交即属本变更**，共 **21 个**（`51c1cf9` → `c31fe14`），对它们求**路径并集**再与允许集比对
  - **结果**：并集为 `pyproject.toml`、`.pre-commit-config.yaml`、`.github/workflows/`（4 个）、`example/`（3 个）、仓库根 `__init__.py`、`zoo_framework/`（41 个源文件 + `__init__.py`）、`openspec/changes/establish-type-gate/`（2 个）✓ ——**唯一越界项是 `CLAUDE.md`**：它被本变更的 `a0a130c` 一并改到，**不在允许集内**，形态上看是那次 `git add` 把工作区里**既有的** `CLAUDE.md` 改动一并卷了进去（即"`git add <file>` 的粒度是该文件的**全部**改动"那类问题，与 `commit-hook-hazard` 同族）
  - **如何处理（没有改写历史）**：改写历史会让已存在的引用失效且不可核对，故改为**就在本次把 `CLAUDE.md` 改成与事实一致并显式记录**——因为放着不管它正**对本变更撒谎**：其中三条（"mypy 在两个 workflow 里都是 `continue-on-error`"、"`tests.yml` 仍有引用不存在目录的 benchmark 作业"、"`example/main.py` 调 `Master(1)`、`demo_event.py` 从 `build.lib` 导入"）**已全部被本变更改掉**（对应 4.1/4.2、6.4、7.1/7.2）。顺带把版本那句里**每次发版就会腐坏**的具体取值删掉（改为不含取值、只讲机制与校验方式）。**这是一处刻意的、记录在案的偏离**，理由是"变更的产物文档不得对本变更的结果撒谎"
  - **依赖**：`[project].dependencies` 在**本变更的提交里从未改动**（本变更只在 `6ba007c` 动过 `pyproject.toml`，加的是 `[tool.mypy.overrides]`）✓ **无新增运行时依赖**。（`jinja2` 被移除是**合并进来的** CLI 重构所为，不是本变更。）

---

## 重取基线结论（本节的元记录）

重取基线时发现**原始任务表把若干前提写成了已完成或未变**，实测不符：1.1 的两条断言一条部分为假、一条不成立；6.2 的理由（"当前必失败"）因 Pages 启用与 `mkdocs.yml` 落地而过期；6.3 只完成了一半却被记为整条；6.1/7.3/7.4/7.5 确已完成但表中未标；分类"第三方存根缺失"**按配置恒为空**；另有两条**本变更自己造成的耦合**原表不可能有（4.6 的本地钩子、7.6 的版本值）。

**这是同一族问题的又一次实例**：把"我以为的状态"写成断言，而它与事实不符。本仓库这一轮已因此改过三份规范（全称断言为假、载体枚举不全、MODIFIED 漏带 Scenario）。故本表的处理方式沿用同一取向——**不靠记得更新，靠每次执行前重新取事实**：1.2 的存在意义就是每轮重取基线，而**这次重取恰好证明了它必要**。

**一处刻意的克制**：本表**不**给出"已完成/未完成"的总计数（如"5/31 已完成"）。计数是手维护事实，本仓库已实测它会漂移（任务书估"六处"载体、实得七处）。状态以每个条目前的标记为准，读者可按标记现数。
