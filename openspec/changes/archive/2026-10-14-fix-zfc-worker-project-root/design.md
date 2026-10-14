## Context

`worker_func` 会在输出目录旁寻找 `main.py`，并在其中注册新增 Worker。项目外部即使成功创建 `workers/<name>_worker.py`，也没有入口导入该文件，因此该次调用只留下不可用文件。

## Decision

将 `src/main.py` 作为项目根目录的唯一判据。它是脚手架生成的 Worker 注册入口；`config.json` 不是注册所需文件，单独要求它会无故拒绝仍可运行的项目。若当前目录和所有父目录都没有该入口，则抛出 `click.ClickException`。异常在创建输出目录之前抛出，因而失败时不产生文件或目录。

查找从当前目录开始并向父目录进行，选择最近的匹配项。这样从项目根、`src/` 或项目内的子目录执行时，Worker 都写入同一个 `<project>/src/workers/`。返回相对于原工作目录的路径，保留现有 CLI 调用方式；接线入口路径则从 Worker 目录的绝对路径推导，避免在 `src/workers/` 内执行时误把入口定位到 `workers/main.py`。

`zfc --create` 与 `--worker` 的组合调用已有显式 `project_dir`，继续绕过当前目录搜索并写入本次创建项目。名称校验、重复名称策略和项目创建行为均不变。

## Error

找不到入口时提示缺少 `src/main.py`，并给出 `zfc --create <name>` 或切换到现有项目目录的下一步。测试验证非零退出、错误提示以及目录快照完全不变（快照同时登记文件与目录——只记文件时"留下一个空 `workers/` 目录"不可见）。

## Language

用户可见文案遵循变更 `api-docstring-english`（`cross-platform-io` 的 SHALL：框架自身的用户可见控制台输出 MUST 为英文）。因此本变更新增的报错消息为英文，`resolve_worker_dir` 的 docstring 保持该变更已完成的英文化——它在 `zoo_framework.cli.__all__` 导出面内，`help()` / IDE 悬浮可见。OpenSpec 正文与测试文件维持中文。

## Non-goals

- 不校验 `config.json` 的内容或要求该文件存在。
- 不让 `--worker` 自动创建新项目，也不添加 CLI 选项。
- 不改变已存在脚手架项目的 Worker 命名、模板或接线行为。
- 不修 `--create` 的同类问题（issue #131 第 4 点）：目标路径不可创建时它抛裸异常栈（实测 `zfc --create ''` → `FileNotFoundError`、`zfc --create 'a<b'` → `OSError`）。该缺陷违反 `cli-scaffolding` 既有的「MUST NOT 向调用方暴露未捕获的异常栈」，是存量问题，与「Worker 必须落在脚手架项目内」这条不变量无关，另立变更处理。
