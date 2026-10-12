# 写一个原生任务（Native Task SDK）

> **先读这条**：原生扩展是**可选的独立发行物**（`pip install zoo-framework[native]`），
> 主包不依赖它。不装它时框架一切如旧；请求原生能力时显式报错，不静默回退。

本页面向「想往下加一个原生任务」的人。可编译的起点在 `native/template/`——复制整个目录到
仓库外，改 crate 名与任务名即可；机械校验用 `native/validate_contract.py`。

## 契约：四个入口

扩展模块（cdylib）MUST 暴露四个入口，适配器 `zoo_framework.native.adapter.NativeAdapter`
按名调用：

| 入口 | 形状 | 约定 |
|---|---|---|
| `contract_version()` | `-> int` | MUST 等于框架的 `CONTRACT_VERSION`；主版本不匹配时适配器拒绝加载 |
| `capabilities()` | `-> list[str]` | MUST NOT 声明适配器不支持的能力（当前不支持 `internal_parallel` / `zero_copy`）；首版留空是诚实的默认 |
| `tasks()` | `-> dict[str, NativeTaskContract]` | 值 MUST 是**框架侧 `NativeTaskContract` 的真实实例**——适配器按属性访问读字段，返回 dict 会在执行路径上炸 |
| `execute(task, payload)` | `(str, bytes) -> bytes` | payload 是输入字节，返回值是输出字节（v1 约定为 JSON）；失败 MUST 按下面三族抛异常 |

`NativeTaskContract` 的位置字段序（扩展侧构造时的参数顺序）：
`name, contract_version, input_format, max_input_bytes, output_format, error_classes, capabilities`。

## 错误分类：三族

| 族 | 语义 | 谁抛 |
|---|---|---|
| `NativeInvalidInput` | 任务**根本没开始跑**（长度、结构、未注册任务名） | 扩展侧执行前拒绝 |
| `NativeTaskFailed` | 任务跑了并给出**受控业务结论**（校验和不符、功能码不支持等） | 扩展侧执行体 |
| `NativePanic` | 非受控异常 | PyO3 在 FFI 边界把 Rust panic 转成 `PanicException`，适配器兜底映射 |

**纪律**：`panic = "unwind"` MUST 保持（PyO3 依赖它把 panic 转成异常，而不是 abort 进程）。
`catch_unwind` 不是进程隔离——它挡不住 abort、段错误、内存破坏或 OOM。需要硬隔离请走独立
进程，不属于本契约。

受控业务失败 MUST NOT 用 panic 或通用异常表达——那会被兜成 `NativePanic`，把「业务说不」
伪装成「扩展坏了」。

## 执行纪律

- **执行期间离开解释器**：用 `py.detach(..)`（PyO3 0.25 起 `allow_threads` 的新名字）。
  这是多核伸缩的机制前提——实测 12 线程饱和形状 8.43x。
- **执行体不回调 Python**：粗粒度任务，一次跨界完成全部工作（跨界成本约 29ns，可忽略）。
  把「过滤 → 聚合」拆成多次 Python↔Rust 往返，会把收益全部还回去。
- **输入所有权**：`payload` 是 `bytes` 的借用切片，`detach` 期间不得把它交给别的线程；
  需要跨线程就用自有缓冲区。

## 契约演进规则

- `CONTRACT_VERSION` 的**主版本**变化 = 破坏性变更（入口增删、错误族语义变化）→ 适配器
  MUST 拒绝版本不匹配的扩展，而不是尽力而为。
- 新增一个**任务**不是契约变更：在 `tasks()` 里多注册一项即可，版本号不动。
- 新增一个**能力**（如未来的 `zero_copy`）是契约变更：先让适配器认识它，再允许扩展声明。
  提前声明未实现的能力会让调用方按错误的前提编程。

## 该不该下沉：判断表

数据来自 `native/DECISION.md`（含包络重测）。**先看形状，再看任务**。

| 判据 | 该下沉 | 不该下沉 | 实测依据 |
|---|---|---|---|
| 输入规模 | 帧 ≥3 寄存器（**≥11 字节**） | <11 字节 | 11B 1.57x、13B 1.91x、15B 2.19x、21B 2.82x、255B 9.63x；7B 1.00x、9B 1.29x（未过 1.5x 门槛） |
| 主要成本在哪 | 纯 CPU 循环、逐字节处理 | 已被 C 库顶住（`hashlib`/`regex`/`cryptography`） | 被 C 库顶住时上限约 1.5–3x |
| 是否回调 Python | 无回调，一次跨界完成 | 需要回调 Python 取数据或做判断 | 跨界 + 回调会把收益还回去 |
| 调用粒度 | 粗粒度、可批量 | 极短小动作、逐条调用 | 适配链有 **~2.9µs 固定地板**（契约查询、上限检查、`bytes()` 复制、`json.loads`） |
| 批量形状 | 大帧批处理（K=64：10.34x） | 小帧批处理（K=8×1reg：1.09x） | `native/results/stage2_acceptance.json` |

**渐近上限**：帧越大收益越高，但**不是无限**——255 字节实测 9.63x，模型外推的渐近上限约
12x。承诺「几十倍」是不诚实的。

**先量再说**：判断表是**粗筛**。真要下沉，按 `native/DECISION.md` 的方法在**同一次运行内**
做四链路对照（P1 纯 Python / P2 C 原语 / P3 Rust 直调 / P4 适配链），别拿跨运行的数字相减。

## 校验器

```bash
python native/validate_contract.py native/template          # 正例：应输出「契约校验通过」
```

它做四件事：`cargo build --release`、把产物改名后导入、逐条核对上文的四条纪律、退出码 0/1。

**对故意写错的 crate 报错**（可复现的演示）：

```bash
cp -r native/template /tmp/broken && cd /tmp/broken
sed -i 's/const CONTRACT_VERSION: u32 = 1;/const CONTRACT_VERSION: u32 = 99;/' src/lib.rs
python <repo>/native/validate_contract.py /tmp/broken --expect-fail
```

实测输出（2026-10-12，Windows 本机）：

```text
契约校验未通过（1 项）：
  - contract_version() = 99，框架的 CONTRACT_VERSION = 1（主版本不匹配时适配器会拒绝加载）
```

> 注意：若把副本的 `CARGO_TARGET_DIR` 指到模板自己的 target，会**覆盖模板的产物**
> （两个 crate 同名同路径）。演示后需 `cargo clean` 再重建模板，否则正例会误读坏产物——
> 这也是正例进 CI、负例只作文档演示的原因。

## 相关

- [`native/DECISION.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/native/DECISION.md) —— go 结论、工作包络、读数边界
- [`docs/api/native.md`](api/native.md) —— 适配器与契约的 API 参考
- go 结论的可安装化（CI / abi3 / wheel）见 issue #129
