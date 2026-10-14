# 原生扩展发布验证 runbook

> 面向**维护者**。本页把「CI 能自动证明的」与「只有索引账号所有者能做的」分开列清，
> 每一步都给出可复现的命令与通过判据。关联：issue #129、`native/DECISION.md` 的
> 「发行」一节、`.github/workflows/native.yml`（构建 + 加载闸门）、
> `.github/workflows/native-release.yml`（发布闸门）。

## 1. 一版发布要过的三道闸门

| # | 闸门 | 载体 | 谁来做 | 通过判据 |
|---|---|---|---|---|
| 1 | 构建 + 加载 | `.github/workflows/native.yml` | CI 全自动 | 三平台 `cargo test` + 原生 pytest 全绿；一份 abi3 wheel 在 3.11 与 3.13 上加载**同一产物** |
| 2 | 发布 | `.github/workflows/native-release.yml` | CI 全自动（OIDC，无长期 token） | tag 推送或手动触发后，索引上出现该版本的 wheel |
| 3 | 安装 + 派发 | 临时 venv + `pip install "zoo-framework[native]"` | 半自动（第 4 节） | 扩展可导入、`native:enabled=true` 能派发一个原生任务 |

## 2. 现状（2026-10-13 实测）

| 项 | 事实 | 证据 |
|---|---|---|
| 闸门 1 | 三平台绿 + abi3 同产物双版本加载 | `gh run view 38339077692 --json jobs`（`main`，合并 PR #225，`success`） |
| 闸门 2 | 发布成功但**产物收全场不完整**：PyPI 上只有 Windows wheel | `zoo-framework-native` 0.1.0 的 `releases` 只有 `zoo_framework_native-0.1.0-cp311-abi3-win_amd64.whl` |
| 闸门 3 | Windows x86_64 + CPython 3.11 端到端通过（第 4 节） | 本机临时 venv 实测，见第 4 节输出 |
| TestPyPI 演练 | 从未跑过 | `native-release.yml` 的 3 次运行里没有任何一次执行过 `Publish to TestPyPI` 步骤 |

## 3. 闸门 1：CI 构建与加载（全自动）

```bash
gh run list -w native.yml -L 5 --json databaseId,conclusion,headBranch,createdAt,status,event
gh run view <databaseId> --json jobs
```

2026-10-13 在 `YearsAlso/zoo-framework` 的实测：`main` 上最近一次**已完成**的运行是
`38339077692`（合并 PR #225），结论 `success`，六个作业全绿：

- `cargo test + native pytest (ubuntu-latest | macos-latest | windows-latest)` —— 三平台矩阵
- `build abi3 wheel` —— 含「Assert the wheel is abi3」步骤（wheel 文件名里没有 `abi3` 标签即失败）
- `same wheel on Python 3.11` / `same wheel on Python 3.13` —— 两者都
  `actions/download-artifact` 取 `wheel` 作业上传的 `native-wheel`，**不重新构建**

「一份 wheel 覆盖两个解释器」因此是工作流结构保证的，不是断言上的巧合。同一工作流的另一次
运行（`38406109201`，分支 `fix/native-release-fan-in`）也已完成，结论 `success`，六个作业
同样全绿。

> **CI 不产出性能数字。** `native.yml` 只跑 `cargo test` 与原生 pytest，没有 benchmark 作业。
> 所以 **Linux / macOS 的收益包络仍未测**，`native/DECISION.md` 的 5.3 平台表按「CI 已接入，
> 性能形状未测」如实标注。要拿到数字，需要新增一个性能作业，或在有 `cargo` + `maturin` 的
> Linux / macOS 机器上按 `native/DECISION.md` 的读数纪律复测——那是后续变更，不在本页范围。

## 4. 闸门 3：端到端安装验证

在一个**空** venv 里从 PyPI 安装已发布的 `zoo-framework[native]`，确认扩展可加载、开关可用、
原生任务能被派发并给出正确结果。

```bash
# 1) 建一个临时 venv；用 3.11 顺带验证 abi3 wheel 在低于 CI 3.13 的解释器上也加载同一份产物
E2E=$(mktemp -d)
uv venv --seed --python 3.11 "$E2E/.venv"

# 2) 从 PyPI 安装（读的是索引上的真实产物）
#    Windows 解释器路径是 "$E2E/.venv/Scripts/python.exe"，POSIX 是 "$E2E/.venv/bin/python"
"$E2E/.venv/bin/python" -m pip install "zoo-framework[native]"

# 3) 打开开关（Master 读工作目录下的 ./config.json）
cd "$E2E"
printf '{"native":{"enabled":true}}\n' > config.json
```

```bash
# 4) 派发一个原生任务并核对结果
"$E2E/.venv/bin/python" - <<'PY'
import sys, time
import zoo_framework, zoo_framework_native

print("sys.version:", sys.version.split()[0])
print("zoo_framework version:", getattr(zoo_framework, "__version__", "n/a"))
print("zoo_framework_native file:", zoo_framework_native.__file__)
print("contract_version:", zoo_framework_native.contract_version())
print("capabilities:", list(zoo_framework_native.capabilities()))
print("tasks:", sorted(zoo_framework_native.tasks()))

from zoo_framework.core.params_factory import ParamsFactory
print("native:enabled ->", ParamsFactory().get_params("native:enabled", default_value=False))

from zoo_framework.core import Master
from zoo_framework.core.master import MasterConfig
from zoo_framework.native import NativeTaskWorker
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor

# 一条合法 Modbus RTU 响应帧：地址 0x01 / 功能码 0x03 / 数据 2 字节 0x1234 / CRC 0xB533
frame = bytes.fromhex("0103021234b533")


class ParseNative(NativeTaskWorker):
    def __init__(self):
        super().__init__({"name": "ParseNative", "is_loop": False, "delay_time": 0,
                          "task_name": "modbus_rtu.parse_response", "input": frame})


delivered = []
reactor = WaiterResultReactor()
reactor.worker_names = None
reactor.on_result = delivered.append
EventReactorManager().bind_topic_reactor("waiter", reactor)

master = Master(MasterConfig(enable_svm=False))
try:
    master.register_worker("ParseNative", ParseNative)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not delivered:
        master.waiter.execute_service()
        time.sleep(0.01)
    print("delivered count:", len(delivered))
    for r in delivered:
        print("result.content:", r.content)
finally:
    master.shutdown()
PY
```

**2026-10-13 实测输出**（Windows x86_64，临时 venv CPython 3.11.15）：

```text
sys.version: 3.11.15
zoo_framework version: 0.13.0
zoo_framework_native file: ...\site-packages\zoo_framework_native\__init__.py
contract_version: 1
capabilities: []
tasks: ['modbus_rtu.parse_response']
native:enabled -> True
delivered count: 1
result.content: {'slave': 1, 'function': 3, 'byte_count': 2, 'registers': [4660]}
```

`4660` 即 `0x1234`。派发**恰好一次**，结果经既有单一结算点投递。

**平台限制（如实记录）**：PyPI 上 `zoo-framework-native` 0.1.0 目前**只有**
`cp311-abi3-win_amd64.whl`（核对命令见第 5 节）。因此 `pip install "zoo-framework[native]"`
在 **Linux / macOS 上会因为没有匹配的 wheel（也没有 sdist）而失败**——这是第 5 节 fan-in
缺口的直接后果，不是扩展本身在那些平台上不可用。

## 5. 闸门 2：发布流水线与 fan-in 缺口

```bash
gh run list -w native-release.yml -L 5 --json databaseId,conclusion,headBranch,event,status
gh run view <databaseId> --json jobs
```

索引核对（列出某版本的全部产物）：

```bash
curl -s https://pypi.org/pypi/zoo-framework-native/json | python -c "import sys,json; d=json.load(sys.stdin); print('latest:', d['info']['version']); [print('  ', f['filename'], f['upload_time']) for f in d['releases'][d['info']['version']]]"
```

**实测（2026-10-13）**：`latest: 0.1.0`，只有一个文件
`zoo_framework_native-0.1.0-cp311-abi3-win_amd64.whl`。

时间线（`gh run view 38357074578 --json jobs`，tag `v0.13.1-beta`）：

| 时间（UTC） | 事件 |
|---|---|
| 06:30–06:31 | `build wheel (manylinux)` / `(macos-latest)` / `(windows-latest)` 三个作业全绿 |
| 13:13–13:14 | `publish to pypi` 作业被**重跑**；`Publish to PyPI` 成功（OIDC，无长期 token） |

三个构建作业都成功，索引上却只有一份 wheel——证据指向**产物收全场（fan-in）缺口**：
`build-linux` 与 `build-cross`（macOS + Windows）都往**同一个** artifact 名 `native-wheels`
上传（见 `.github/workflows/native-release.yml`），`publish` 作业再 `download-artifact`
取 `native-wheels`，于是只能拿到其中一部分。该缺口正在分支 `fix/native-release-fan-in`
上修（提交标题：每作业唯一产物名 + 数量闸门）；该分支的 `native.yml` 运行 `38406109201`
已完成且结论 `success`（六个作业全绿），即构建/加载闸门在修复分支上仍然成立。
**修好并合并之前，任何一次真实发布都可能只发出部分平台产物。**

> 本轮核对**无法**读到步骤级日志：`gh run view <id> --log` 与 `gh api .../jobs/<id>/logs`
> 在本机都因连不上 GitHub Actions 的日志存储（`*.blob.core.windows.net`、
> `results-receiver.actions.githubusercontent.com`）而失败。因此上面的结论只依据
> **运行 / 作业元数据**（`--json jobs`）与**索引真源**（PyPI JSON）——这两条也正是复现时
> 应当引用的命令。

## 6. 剩余账号侧动作（需维护者操作）

下面两步**无法**由 CI 或本仓库内任何脚本自动完成，必须由持有索引账号者执行。在它们完成前，
**不得**声称「TestPyPI 演练通过」或「三平台发布链路完整」。

### 6.1 TestPyPI 侧 trusted publisher 注册

- **为什么需要**：TestPyPI（`test.pypi.org`）是与正式 PyPI **相互独立**的索引，trusted
  publisher 必须在那边**单独**注册；PyPI 上已注册不覆盖 TestPyPI。
- **做法**：登录 `https://test.pypi.org` → 账号设置 → Publishing → 新增 trusted publisher，
  字段与 `.github/workflows/native-release.yml` 的 `publish` 作业**逐字对齐**：
  - PyPI Project Name：`zoo-framework-native`
  - Owner：`YearsAlso`
  - Repository name：`zoo-framework`
  - Workflow name：`native-release.yml`
  - Environment name：`pypi`（对应工作流里的 `environment: pypi`）
- **验收判据**：手动触发一次演练（6.2）后，`Publish to TestPyPI` 步骤**不是 `skipped`** 且成功，
  且 `https://test.pypi.org/pypi/zoo-framework-native/<version>/json` 返回 200，其
  `releases[<version>]` 的文件集合与本次构建的平台产物一致。

### 6.2 TestPyPI 演练（dry run）

```bash
gh workflow run native-release.yml -f target=testpypi
gh run list -w native-release.yml -L 1 --json databaseId,status,conclusion
gh run view <databaseId> --json jobs
```

- **验收判据 1**：`Publish to TestPyPI` 步骤执行且成功（不是 `skipped`）。
- **验收判据 2**：TestPyPI 索引上出现该版本，产物集合 = 本次构建的平台产物集合。
- **验收判据 3（负向）**：演练**没有**写入正式 PyPI（`pypi.org` 上该版本不变）。
- 注意：发布步骤带幂等闸门——同名版本已存在于目标索引时 `exists=true`，发布步骤会被跳过；
  演练因此要用一个目标索引上不存在的版本号，或先确认该版本在 TestPyPI 上确实不存在。

### 6.3 正式 PyPI 侧 trusted publisher：已有成功证据，核对即可

与 6.1 / 6.2 不同，**正式 PyPI 侧**的 trusted publisher 已经有成功发布的证据：运行
`38357074578` 的 `publish to pypi` 作业在 2026-10-13 13:14 用 OIDC（`id-token: write`，
无长期 token）把 `zoo-framework-native 0.1.0` 上传成功。

仍需维护者核对的是**配对关系**：publisher 登记的（Owner / Repository / Workflow name /
Environment）必须与 `.github/workflows/native-release.yml` 里 `publish` 作业当前声明一致。
任何一次重命名发布作业、改工作流文件名或改 `environment:` 都会让下次 OIDC 换 token 失败
（403），而该失败只在**下一次真实发布**时才暴露。

- **验收判据**：下一次真实 tag 发布的 `Publish to PyPI` 成功（依赖第 5 节的 fan-in 修复），
  且 PyPI 索引上的 wheel 文件集合 = 三平台产物。

## 7. 复现清单（一页速查）

```bash
# 闸门 1：构建 + 加载
gh run list -w native.yml -L 5 --json databaseId,conclusion,headBranch,createdAt,status,event
gh run view <id> --json jobs

# 闸门 2：发布元数据 + 索引上的产物集合
gh run list -w native-release.yml -L 5 --json databaseId,conclusion,headBranch,event,status
gh run view <id> --json jobs
curl -s https://pypi.org/pypi/zoo-framework-native/json | python -c "import sys,json; d=json.load(sys.stdin); print(d['info']['version'], [f['filename'] for f in d['releases'][d['info']['version']]])"

# 闸门 3：端到端安装 + 派发（第 4 节的两段脚本）
```

## 相关

- `native/DECISION.md` —— go 结论、工作包络、5.3 平台表、「发行」一节
- `docs/native-tasks.md` —— 写一个原生任务（契约、错误族、执行纪律）
- issue #129 —— 把 go 结论变成可安装、可验证的交付物
