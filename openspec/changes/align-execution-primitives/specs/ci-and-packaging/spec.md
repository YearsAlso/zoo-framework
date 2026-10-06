## Purpose（本变更新增条款）

让 `bench/` 的测量在三平台原生环境可周期性取得；并把"运行依赖不含需源码构建的 greenlet 系包"固化为安装可复现性的可验证情形。

## MODIFIED Requirements

### Requirement: 开发环境安装 MUST 可复现

项目 SHALL 提供可成功执行的开发环境安装路径。锁定文件声明的 Python 版本要求 MUST 与项目元数据一致；锁定文件中的依赖 MUST 在项目声明的 Python 版本上可安装。运行依赖 MUST NOT 包含在项目声明的 Python 版本上无预构建产物、需源码编译的包（本条款落地时表现为 gevent / greenlet 整体移出依赖树）。

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

#### Scenario: 运行依赖中不含 greenlet 系包
- **WHEN** 检查安装后的依赖树与锁定文件
- **THEN** gevent 与 greenlet 均不在其中，任何 Python 3.13 构建（含 free-threaded）上安装不触发源码编译

## ADDED Requirements

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
