## 破坏性变更（`zfc` 脚手架命令）

仓库无 CHANGELOG，`release.yml` 生成的 GitHub Release 正文取自 `git log` 的提交信息，
因此以下文本需在提交时原样并入提交信息正文。

### `zfc --create <name>`：目标已存在时由静默 `exit 0` 改为报错

以前：目标目录已存在时命令直接返回，退出码 0、无任何输出。调用方无法区分"本次创建了"
与"本来就存在"，把路径写错也看不出来。

现在：以退出码 1 失败并指明目标已存在，且不改动任何既有文件。脚本中需要幂等时请自行
先判断目录是否存在。

### `zfc --worker <name>`：非法名称由"成功但产出坏代码"改为报错

以前：`my-task` / `123task` / `my task` 这类名称会被直接拼进类名与模块名，产出的文件
无法解析（`SyntaxError`），而命令**退出码仍是 0**——用户拿到一个启动即崩、且不知道
哪里错了的工程。

现在：名称必须是合法 Python 标识符（不以数字开头，不含连字符、点号或空格，不是 Python
关键字），否则以退出码 2 失败且不产出任何文件。请改用下划线命名（`my_task`）。

### 其他行为变更（非破坏性）

- `zfc --create a/b` 现在会创建缺失的父目录，不再抛 `FileNotFoundError` 栈。
- `zfc --create X --worker Y` 一次调用中，`Y` 现在落在 `X/src/workers/` 并被 `X` 的入口
  注册。此前 `Y` 会落到当前工作目录下的 `workers/`，而 `X/src/main.py` 的注册表为空。
- 对同一名称重复执行 `zfc --worker` 现在是幂等的，不再向入口重复追加导入行与注册条目。
- 脚手架产出的 `src/conf/` / `src/params/` / `src/events/` 不再是空占位包，各自含一个
  可加载的示例模块（`@configure` / `@params` / `@event`），并被生成的入口实际导入；
  `config.json` 相应新增 `demo.greeting` 一项。
