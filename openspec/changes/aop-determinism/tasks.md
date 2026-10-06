## 1. 规格

- [x] 1.1 新增 `aop` 能力规格（`@configure` 注册/消费/封契约、`@logger`、`@stopwatch`、`@params` 载入顺序核对、不提供项声明）；验证：`openspec validate --all` 绿

## 2. 顺序耦合的出声机制

- [x] 2.1 `ParamsFactory` 增载入世代计数（成功读入配置 +1，`generation()` 查询）；`@params` 解析时记录世代
- [x] 2.2 `Master.__init__` 读到非零世代配置后核对 `stale_param_classes()`，有冻结类则 `RuntimeError` 点名（含修正指引）；验证：`tests/test_aop_determinism.py` 三态用例（冻结报错 / 无配置放行 / 正常用法不误伤）通过
- [x] 2.3 `@configure` 封位：`Master._load_config` 消费后置封；封后注册照常登记并发 `LogUtils.warning`；验证：封后告警用例 + 脚手架 `assertions_survive_prior_runs` 契约用例通过
- [x] 2.4 对 issue #51 原文两处修正的裁定记录（proposal 的 Why 末段 + 规格条款措辞）：解析现场拦截被包根即时导入证伪；封后硬报错被脚手架重复运行契约证伪——均按实测证据调整

## 3. 测试接缝与门禁

- [x] 3.1 conftest 复位接缝：封位解封 + 世代/解析记录清零（每项均已注明属 #50 待收编的进程级状态）
- [x] 3.2 全量门禁：pytest 694（687 + 7 新用例）只增不减、mypy 0 error、ruff/bandit 绿；CHANGELOG 记 BREAKING（窄，冻结用法报错）

## 4. 联动

- [ ] 4.1 PR 合并后：关闭 #51（附规格位置与不可行点修正说明）；#50 登记表追加两项新状态（`ParamsFactory._generation`、`aop.params._resolved_generation`）；#32 在办表同步
