# ci-and-packaging Specification

## Purpose
定义持续集成作业与其声明输入之间的一致性、开发环境安装的可复现性、示例代码的可运行性，以及版本控制对构建产物的排除。该能力针对的失效模式是"配置里声明了，但从不生效或以静默方式失败"。

## Requirements

### Requirement: 开发环境安装 MUST 可复现

项目 SHALL 提供可成功执行的开发环境安装路径。项目元数据声明的 Python 下界 MUST 由仓库内可复现的证据支撑（最低可行版本的调研结论与在该解释器上实际运行测试的结果），MUST NOT 仅由历史默认值或习惯决定。锁定文件声明的 Python 版本要求 MUST 与项目元数据一致；锁定文件中的依赖 MUST 在项目声明的 Python 版本上可安装。静态检查工具的 target 版本配置、持续集成的测试矩阵与文档中的门槛声明 MUST 与该下界来自同一真源。运行依赖 MUST NOT 包含在项目声明的 Python 版本上无预构建产物、需源码编译的包（本条款落地时表现为 gevent / greenlet 整体移出依赖树）。

#### Scenario: 按锁定文件安装成功

- **WHEN** 在项目声明的 Python 版本上按锁定文件同步依赖
- **THEN** 同步成功完成，不出现构建失败

#### Scenario: 版本要求一致

- **WHEN** 比较锁定文件与项目元数据中声明的 Python 版本要求
- **THEN** 两者一致

#### Scenario: 锁定文件的依赖在目标版本上有可用产物

- **WHEN** 检查锁定文件中含本地扩展的依赖在项目声明的 Python 版本上是否有可用产物
- **THEN** 该依赖有可用产物，或已被升级到有可用产物的版本

#### Scenario: 元数据安装路径同样可用

- **WHEN** 以可编辑模式安装项目及其开发依赖
- **THEN** 安装成功完成

#### Scenario: 下界有可复现的证据

- **WHEN** 复核元数据中声明的 Python 下界
- **THEN** 仓库内能给出该下界的调研结论（使用了哪些语言特性与标准库 API 的扫描证据，以及在下界解释器上实际运行测试套件的结果），且 `docs/` 中写有该下界的依据

#### Scenario: 工具链与文档指向同一下界

- **WHEN** 比较元数据的 `requires-python`、静态检查工具的 target 版本配置与文档中的门槛声明
- **THEN** 三者指向同一版本，不出现"元数据声明某个版本、工具按另一版本检查、文档写第三个版本"的分叉

#### Scenario: 运行依赖中不含 greenlet 系包

- **WHEN** 检查安装后的依赖树与锁定文件
- **THEN** gevent 与 greenlet 均不在其中，任何受支持的 Python 构建（下界起，含 3.13 free-threaded）上安装不触发源码编译

### Requirement: CI 作业 MUST 校验其声明的输入存在

依赖特定文件或目录的持续集成步骤 SHALL 在该输入缺失时跳过自身，MUST NOT 以失败告终。与该步骤配套的后续步骤 SHALL 采用相同的存在性条件。

#### Scenario: 依赖文件缺失时跳过而非失败
- **WHEN** 某个作业依赖的配置文件或目标目录在仓库中不存在
- **THEN** 该作业被跳过，且不以失败状态结束

#### Scenario: 配套步骤采用相同条件
- **WHEN** 某个作业因输入缺失被跳过
- **THEN** 与其配套的产物上传步骤同样被跳过

### Requirement: CI 声明的参数 MUST 被实际使用

持续集成配置中声明的参数 SHALL 被对应步骤实际使用，MUST NOT 出现"声明了变量、步骤却使用硬编码值"的情形。被测试的 Python 版本 MUST 来自单一真源。测试矩阵 MUST 覆盖元数据声明的下界，且该下界 MUST 在 ubuntu / windows / macos 三平台各被完整测试一次。

#### Scenario: 测试矩阵的版本被用于安装步骤

- **WHEN** 测试作业声明了 Python 版本矩阵
- **THEN** 安装 Python 的步骤使用该矩阵中的值

#### Scenario: 下界在三平台各被完整测试

- **WHEN** 读取测试作业的矩阵
- **THEN** 元数据声明的下界在被支持的所有平台上各出现一次，且这些作业运行完整测试套件

#### Scenario: 指定的测试目标目录存在或作业被跳过

- **WHEN** 某个作业指定了测试目标目录
- **THEN** 该目录在仓库中存在，或该作业在目录缺失时被跳过

### Requirement: 安全扫描 MUST 使用实际存在的配置

安全扫描工具 SHALL 被指向包含其配置的文件。所引用文件 MUST 存在，且 MUST 包含该工具的配置节。

#### Scenario: 扫描命令引用的配置存在且含配置节
- **WHEN** 执行安全扫描
- **THEN** 所引用的配置文件存在且包含该工具的配置节

#### Scenario: 本地钩子与持续集成指向同一份配置
- **WHEN** 比较本地提交钩子与持续集成所用的扫描配置路径
- **THEN** 两者指向同一份配置文件

### Requirement: 仓库内的示例 MUST 可被运行

仓库内提供的示例代码 SHALL 能被实际执行。示例 MUST NOT 从构建产物路径导入，MUST NOT 以与公开接口不符的方式构造框架对象。

#### Scenario: 示例入口可执行
- **WHEN** 按示例自身声明的方式运行示例入口
- **THEN** 示例启动成功，不抛出异常

#### Scenario: 示例不从构建产物路径导入
- **WHEN** 检查示例代码的导入语句
- **THEN** 所有导入都指向安装后的包或标准库，不指向构建输出目录

### Requirement: 版本控制 MUST NOT 跟踪构建产物与虚拟环境

版本控制 SHALL 排除字节码缓存、构建输出与虚拟环境目录。忽略规则 MUST 覆盖这三类路径。

#### Scenario: 已跟踪文件中不含构建产物
- **WHEN** 列出所有被版本控制跟踪的文件并筛选字节码缓存、构建输出与虚拟环境路径
- **THEN** 结果为空

#### Scenario: 忽略规则覆盖各产物类别
- **WHEN** 读取忽略规则
- **THEN** 其中包含字节码缓存、构建输出与虚拟环境三类路径

### Requirement: bench 测量 MUST 可在 CI 三平台原生取得

仓库根 `bench/` 的测量脚本 SHALL 在 CI 上具备可执行路径：原生 Linux、macOS 与 Windows 三平台 MUST 能周期性取得数据（手动触发与定时触发均可），且测量结果的波动 MUST NOT 门禁功能开发。原始测量输出 MUST 作为可下载的构件保留。涉及跨线程唤醒的取数 MUST NOT 在 WSL2 上进行。该作业 MUST NOT 依赖 Rust 工具链（探针对照脚本不在 CI 运行）。

#### Scenario: 三平台各自产出留档
- **WHEN** 在 CI 上运行 bench 作业
- **THEN** 三个平台各自产生带平台标识的测量结果文件并成功上传

#### Scenario: 测量不阻塞功能门禁
- **WHEN** 某平台的测量数字相对历史值回归
- **THEN** 功能测试作业不受影响，bench 作业本身不以失败状态阻断合入

#### Scenario: 无 Rust 工具链也能运行
- **WHEN** 在标准 GitHub runner 上运行 bench 作业
- **THEN** 作业不要求 cargo / maturin，成功完成

### Requirement: 版本线 MUST 跨分支保持连续

发布自动化计算下一版本时，测试分支（dev）的结果 MUST NOT 低于主干（main）的当前声明——以 main 声明为下限，候选低于下限时以下限为基数按同类型重新递增。主干 bump 合并后，自动化 MUST 向测试分支提出 back-merge PR（经人工批准合并，闸门语义不变），使测试分支的声明跟上主干。测试分支收到与主干声明完全一致的"仅版本声明"推送（back-merge 的回声）时 MUST NOT 触发打 tag——同版本号 tag 已存在于主干，重复尝试只会留下失败。发布节奏本身（dev=patch+beta、main=minor）不因本要求改变。

#### Scenario: 分叉被下限拦截
- **WHEN** 主干声明为 0.9.0 而测试分支仍停在 0.8.4-beta，测试分支触发 bump
- **THEN** 计算结果为 0.9.1-beta（沿主干线续算），MUST NOT 产出 0.8.5-beta 等低于主干的版本

#### Scenario: 主干 bump 后自动提出回并
- **WHEN** 主干的版本号 PR 被合并（仅三处版本声明变更）
- **THEN** 自动化打 tag 的同时向测试分支开出 back-merge PR；该 PR 仍需人工批准

#### Scenario: 回声不打 tag
- **WHEN** back-merge PR 合入测试分支（其结果与主干声明完全一致、只动了三处声明）
- **THEN** 不创建 tag、不开新的 bump PR；测试分支下一次内容推送从主干线续算

### Requirement: 文档站产物 MUST 发布仓库根 `llms.txt`

仓库根 `llms.txt` SHALL 是该文件的唯一手写真源；仓库内 SHALL NOT 存在第二份手写副本。

文档站构建 SHALL 把该文件复制到站点产物的**根路径**，使
`https://yearsalso.github.io/zoo-framework/llms.txt` 可达——`llms.txt` 的约定位置正是站点根，
只放在仓库里、取不到该 URL，本要求的发现性目的即落空。

站点产物中的该文件 SHALL 与仓库根真源逐字节一致。

源文件缺失时构建 SHALL 失败，SHALL NOT 静默产出一个不含该文件的站点。

文档部署工作流的触发路径 SHALL 覆盖 `llms.txt`——否则单独更新它的内容不会触发重新发布，
已发布站点会一直带着旧版本（既有 `.well-known/**` 出于同一理由已被列入触发路径）。

#### Scenario: 站点根可达且与真源一致

- **WHEN** 完成一次文档站构建
- **THEN** 站点产物根存在 `llms.txt`，且其内容与仓库根真源逐字节一致

#### Scenario: 真源缺失即构建失败

- **WHEN** 仓库根 `llms.txt` 不存在
- **THEN** 构建以失败告终，不产出缺少该文件的站点

#### Scenario: 只改 `llms.txt` 也会重新发布

- **WHEN** 提交中仅 `llms.txt` 发生变化（文档其他路径未变）
- **THEN** 文档部署工作流被触发

#### Scenario: 不产生第二份手写副本

- **WHEN** 检查仓库内 `llms.txt` 的文件数量
- **THEN** 全仓只有仓库根一份（`docs/` 下不放副本），站点侧的那份由构建期复制产生

### Requirement: 文档站产物 MUST 发布 `.well-known/security.txt`

仓库根 `.well-known/security.txt` SHALL 是该文件的唯一手写真源；仓库内 SHALL NOT
存在第二份手写副本（`docs/` 下不放副本），以免两份内容漂移。

文档站构建 SHALL 把该文件复制到站点产物的 `.well-known/security.txt` 路径，
使 `https://yearsalso.github.io/zoo-framework/.well-known/security.txt` 可达。

> 背景（实测）：mkdocs 会忽略点开头的目录——把文件放在 `docs/.well-known/` 后构建，
> `site/.well-known/` 不产生。因此"在 `docs/` 里放一份"既不可达，又制造第二份副本。

源文件缺失时构建 SHALL 失败，SHALL NOT 静默产出不含该文件的站点。

文档部署工作流的触发路径 SHALL 覆盖 `.well-known/**`——否则单独更新 `Expires`
不会触发重新发布，已发布站点会带着过期文件。

#### Scenario: 构建产物含该文件且与真源逐字节一致

- **WHEN** 执行文档站构建
- **THEN** 产物目录下存在 `.well-known/security.txt`
- **AND** 其内容与仓库根 `.well-known/security.txt` 逐字节一致

#### Scenario: 真源缺失时构建失败

- **WHEN** 仓库根 `.well-known/security.txt` 不存在而构建被触发
- **THEN** 构建以失败结束并指出缺失的源文件
- **AND** 不产出缺少该文件的站点产物

#### Scenario: 触发路径覆盖真源

- **WHEN** 检查文档部署工作流的触发条件
- **THEN** 触发路径包含 `.well-known/**`
- **AND** 因此仅修改该文件也会重新构建并部署

#### Scenario: 不存在第二份手写副本

- **WHEN** 在仓库内检索 `security.txt` 的手写副本
- **THEN** 只有仓库根一份真源
- **AND** `docs/` 下不含 `.well-known/security.txt`（该副本既不可达又会导致漂移）

### Requirement: 许可证元数据 MUST 用 SPDX 表达式声明

`pyproject.toml` SHALL 以 PEP 639 的 SPDX 表达式声明许可证
（`license = "Apache-2.0"`）并用 `license-files` 列出许可证文件；
SHALL NOT 保留 PEP 639 已弃用的 `License :: OSI Approved :: ...` classifier。
`[build-system].requires` SHALL 声明支持 PEP 639 的最低构建后端版本，
使旧后端不会静默产出不符合规范的元数据。

#### Scenario: 声明形式与弃用 classifier

- **WHEN** 读取 `pyproject.toml`
- **THEN** `[project].license` 是 SPDX 表达式字符串且 `license-files` 指向 `LICENSE`
- **AND** `[project].classifiers` 中不存在以 `License ::` 开头的条目
- **AND** `[build-system].requires` 有支持 PEP 639 的最低版本下限

#### Scenario: 构建产物含机器可读许可证

- **WHEN** 构建 wheel 并检查其 `METADATA`
- **THEN** 元数据含 SPDX 许可证表达式与许可证文件条目（如
  `License-Expression: Apache-2.0` 与 `License-File: LICENSE`）
- **AND** 不再只有旧的自由文本 `License:` 字段

### Requirement: 构建与安装 MUST 以真实执行验证

打包元数据变更 SHALL 以真实构建与安装验证，SHALL NOT 仅凭静态检查宣称通过。

#### Scenario: 构建与 twine 校验

- **WHEN** 在仓库根执行 `python -m build`
- **THEN** 产出 sdist 与 wheel 且退出码为 0
- **AND** `twine check dist/*` 对所有产物输出 `PASSED`

#### Scenario: 安装产物可用

- **WHEN** 在干净环境安装构建出的 wheel
- **THEN** `import zoo_framework` 成功
- **AND** 命令行入口（`zfc --help`）可执行

### Requirement: CITATION.cff MUST 存在且版本与真源一致

仓库根 SHALL 提供 CFF 1.2.0 的 `CITATION.cff`，含 `authors`、`title`、`version`、
`license`、`repository-code`、`abstract`；其 `version` SHALL 与
`pyproject.toml` 的版本一致，SHALL 纳入 release 的版本更新步骤（否则即产生
"版本声明漂移"）。校验方式（`cffconvert --validate` 或退化为结构化校验）SHALL
在变更记录中说明。

#### Scenario: 字段完整且与 pyproject 同源

- **WHEN** 解析 `CITATION.cff`
- **THEN** 六个必备字段齐全且 `version` 等于 `pyproject.toml` 的版本
- **AND** 校验结果（工具校验通过，或结构化校验的逐项结论）被记录

#### Scenario: 版本更新不遗漏 CITATION

- **WHEN** release 工作流执行版本更新步骤
- **THEN** `CITATION.cff` 的 `version` 与其它版本声明一起被改写
- **AND** 任一版本声明未被写入新版本号时该步骤失败（不允许开出错的 PR）

### Requirement: 每次 release MUST 附带 SBOM 工件

release 工作流 SHALL 在构建后生成软件物料清单（SPDX-JSON）并作为 release
附件发布；生成失败时工作流 SHALL 失败（SHALL NOT 静默跳过）；SHALL NOT 改变
既有的签名与 PyPI 上传行为。

#### Scenario: SBOM 生成并随附件发布

- **WHEN** release 工作流运行到构建之后
- **THEN** `dist/` 中出现 SBOM 文件
- **AND** release 附件列表包含该 SBOM 文件

#### Scenario: 失败可见

- **WHEN** SBOM 生成步骤失败
- **THEN** 工作流以非零状态结束（不产出"看起来成功但没有 SBOM"的 release）

### Requirement: 打包元数据 MUST 与单一真源保持一致

`pyproject.toml` 的 `keywords`、`classifiers`、`project.urls` SHALL 与
`docs/REPO_METADATA.md` 的投影区保持一致；`readme` 的内容类型声明方式与
`[project.optional-dependencies]` 分组取舍 SHALL 在 design 中说明理由。

#### Scenario: 投影一致

- **WHEN** 比对 `docs/REPO_METADATA.md` 的必需项与 `pyproject.toml` 实际值
- **THEN** 两者逐项一致，无"文档要求含而实现缺失"的条目

#### Scenario: 取舍有记录

- **WHEN** 审阅 design.md
- **THEN** `readme` content-type、urls 齐备性、optional-dependencies 分组三项
  均有明确结论（改或明确不改，附理由）

### Requirement: 运行时依赖 MUST 与实际使用一致

元数据中声明的运行时依赖 MUST 在仓库源码中能找到实际使用（import 或等价引用），MUST NOT 声明没有任何使用证据的依赖。文档中列出或计数的运行时依赖 MUST 与元数据逐项一致（数量与名称），且该一致性 MUST 由机械校验守住。

#### Scenario: 声明的运行依赖都有使用证据

- **WHEN** 逐个检索元数据中每个运行时依赖名在仓库源码中的引用
- **THEN** 每个依赖都能找到至少一处引用；找不到的必须从声明中移除或补上使用

#### Scenario: 文档的依赖清单与元数据一致

- **WHEN** 比较文档中"运行时依赖"清单（含数量）与元数据的依赖列表
- **THEN** 数量与名称逐项一致

### Requirement: 工作流 MUST 显式声明最小权限并钉住 action 版本

`permissions`：每个 workflow SHALL 在顶层显式声明权限，默认只读（`contents: read`
或 `read-all`）；需要写权限的作业 SHALL 只在作业级声明，SHALL NOT 在顶层放开写权限。

`uses`：每个 action 引用 SHALL 钉到 40 位 commit SHA，并以注释标注其语义化标签。
`@v4` 形式一律不合格——**"大部分钉了"不算通过**：只要存在一处 tag 引用，钉 SHA 这一项
即判定为未达成。这一条按"全做或不算做"执行，因为供应链攻击只需要一个未钉的引用。

#### Scenario: 每个工作流都声明顶层权限

- **WHEN** 遍历 `.github/workflows/*.yml`
- **THEN** 每个文件都有顶层 `permissions:` 块
- **AND** 顶层不含 `write`（写权限只出现在作业级）

#### Scenario: 所有 action 引用都钉在 commit SHA 上

- **WHEN** 抽取每个 workflow 中的 `uses:` 引用
- **THEN** 每个引用都指向 40 位十六进制 commit SHA
- **AND** 若在任一 workflow 里留下 `actions/checkout@v4` 这类 tag 引用，机械校验失败

#### Scenario: 写权限仅出现在确实需要写的作业

- **WHEN** 检查声明了作业级写权限的作业
- **THEN** 每处写权限都有其必要性（推分支/tag、上传 SARIF、签发 OIDC 令牌）
- **AND** 状态表如实记录这些作业级写权限是外部审计的剩余扣分项，而不是为刷分把它们删掉

### Requirement: 发布 MUST 走 OIDC 短期令牌并产出可核对来源

发布作业 SHALL 声明 `id-token: write`，SHALL NOT 依赖长期 token：向发布步骤传
`password:` 一律不合格。发布的产物 SHALL 附带可由外部核对的来源或签名（PyPI 上的
PEP 740 证明、`cosign` keyless 签名与证书、SPDX SBOM 三者至少其一）。

发布 SHALL 以测试与质量作业为前提（`needs` 链），SHALL NOT 出现"测试没过也发了版"。

#### Scenario: 发布作业声明 OIDC 权限

- **WHEN** 读取发布 workflow 的发布作业
- **THEN** 该作业声明了 `id-token: write`

#### Scenario: 不传长期 token

- **WHEN** 检查发布步骤的参数
- **THEN** 不传 `password`（长期 PyPI token 不是发布路径的一部分）
- **AND** 机械校验失败于任何把长期 token 接回发布步骤的改动

#### Scenario: 产物带签名与 SBOM

- **WHEN** 检查发布作业的步骤
- **THEN** 存在 SBOM 生成步骤（SPDX）
- **AND** 存在对 `dist/` 产物的 keyless 签名步骤

#### Scenario: 发布以测试与质量为前提

- **WHEN** 读取发布作业的 `needs`
- **THEN** 发布作业依赖测试与质量作业

### Requirement: 依赖漏洞状态 MUST 可复现地复核

依赖真源 SHALL 唯一：`pyproject.toml` 声明依赖、`uv.lock` 锁定版本。仓库内 SHALL NOT
再存在第二份手工维护的依赖清单（历史上 `requirements.txt` 与 `pyproject.toml` 长期漂移，
已删除）。

锁文件 SHALL 与 `pyproject.toml` 保持一致：声明的每个运行依赖 SHALL 能在 `uv.lock` 中
找到对应包条目。对锁定集合的漏洞扫描 SHALL 为 0 命中；复核所用命令 SHALL 记录在
`docs/security-supply-chain.md`，任何人不依赖 CI 也能复跑。

处置结论 SHALL 记入 `CHANGELOG.md` 的 Security 段。

#### Scenario: 不存在第二份依赖清单

- **WHEN** 检索仓库
- **THEN** 不存在 `requirements*.txt`
- **AND** 依赖只由 `pyproject.toml` + `uv.lock` 描述

#### Scenario: 锁文件与 pyproject 同源

- **WHEN** 读取 `pyproject.toml` 的 `dependencies`
- **THEN** 每个声明名都能在 `uv.lock` 的包条目里找到
- **AND** 新增运行依赖但未更新锁文件时机械校验失败

#### Scenario: 锁定集合扫描为零命中

- **WHEN** 对 `uv.lock` 描述的锁定集合执行漏洞扫描
- **THEN** 命中数为 0
- **AND** 复核命令记录在状态表中，可复跑得到同一结论

#### Scenario: 结论记入变更日志

- **WHEN** 读取 `CHANGELOG.md`
- **THEN** 存在 Security 段记录本次依赖漏洞状态复核的结论与钉 SHA 漏项修复
