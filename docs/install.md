# 安装

## 版本要求

| 项 | 值 |
|---|---|
| Python | **3.13 及以上**（`requires-python = ">=3.13"`） |
| 操作系统 | Windows / macOS / Linux |
| 运行时依赖 | `click`、`pyyaml`、`python-dotenv`、`typing-extensions` |

**这是本框架当前的硬门槛。** 若你的环境仍在 3.10–3.12，需要等门槛下调
（见 issue #124），或使用更高版本的解释器。

## 安装

```bash
pip install zoo-framework
```

验证：

```bash
python -c "import zoo_framework; print(zoo_framework.__version__)"
```

## 可选扩展

| 扩展 | 状态 | 说明 |
|---|---|---|
| 原生执行（Rust） | 尚未发布 | `native/` 已通过阶段性验收，但尚未发布到 PyPI，因此当前 `pip install` 无法获得。见 issue #129 |
| 开发依赖 | 可用 | `pip install "zoo-framework[dev]"` |

## 使用 uv 的注意事项

仓库里提交了 `uv.lock`，但**它当前与 `pyproject.toml` 不一致**（实测 `uv lock --check` 报
`The lockfile needs to be updated`）。因此：

```bash
pip install -e ".[dev]"     # 推荐
```

若你偏好 uv，使用 `uv run --no-sync`；**不要**直接 `uv sync`，它会从这个陈旧状态重新解析
并可能改动你的依赖集合。此问题在 issue #115 中跟踪。

## 卸载

```bash
pip uninstall zoo-framework
```

框架运行时会在工作目录产生 `zooStates.pic` 与 `backups/`（状态文件与滚动备份）。
卸载不会删除它们，需要自行清理。
