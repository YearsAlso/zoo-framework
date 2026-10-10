## REMOVED Requirements

### Requirement: 脚手架命令 MUST 依据工作目录结构定位产出目录

**Reason**: 旧规则在工作目录没有源码目录时把 Worker 写入当前目录，可能生成无法从项目入口加载的孤立文件。

**Migration**: 先运行 `zfc --create <name>` 创建脚手架项目，再在项目目录或其子目录运行 `zfc --worker <name>`。

## ADDED Requirements

### Requirement: 新增 Worker MUST 位于最近的脚手架项目

命令行工具新增 Worker 时 MUST 在当前工作目录及其父目录中查找最近的脚手架项目。项目根目录 MUST 由 `src/main.py` 标识；找不到项目入口时，命令 MUST 在任何写入之前以非 0 退出码失败，说明缺少的入口和可继续操作，MUST NOT 创建文件或目录。

#### Scenario: 在项目根目录添加 Worker

- **WHEN** 当前目录包含 `src/main.py`
- **THEN** Worker 写入当前项目的 `src/workers/` 并接入入口

#### Scenario: 从项目子目录添加 Worker

- **WHEN** 当前目录的某个父目录包含 `src/main.py`
- **THEN** Worker 写入最近父目录项目的 `src/workers/` 并接入其入口

#### Scenario: 最近的项目优先

- **WHEN** 当前路径的多个祖先都包含 `src/main.py`
- **THEN** Worker 写入距离当前目录最近的项目

#### Scenario: 仅有源码目录但没有项目入口

- **WHEN** 当前目录或其父目录只有 `src/`，没有 `src/main.py`
- **THEN** 命令失败并且不创建任何文件或目录

#### Scenario: 项目外调用不留下孤立 Worker

- **WHEN** 当前目录及其所有父目录都没有 `src/main.py`
- **THEN** 命令以非 0 退出码失败，提示缺少 `src/main.py` 和运行 `zfc --create <name>` 或切换到项目目录的下一步，且文件系统保持不变

#### Scenario: 输出目录不存在时创建

- **WHEN** 找到项目入口但其 `src/workers/` 目录尚不存在
- **THEN** 命令创建该目录并成功写入 Worker

#### Scenario: 组合创建项目并添加 Worker

- **WHEN** 在一次调用中同时请求 `--create` 与 `--worker`
- **THEN** Worker 写入新项目的 `src/workers/` 并由新项目入口接线，即使命令启动目录不包含脚手架入口

#### Scenario: 判定不依赖进程启动方式

- **WHEN** 以不同方式启动命令，且当前目录或其父目录中的项目结构相同
- **THEN** Worker 始终写入最近项目的 `src/workers/`
