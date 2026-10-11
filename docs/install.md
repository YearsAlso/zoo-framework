# 安装

## 版本要求

| 项 | 值 |
|---|---|
| Python | **3.11 及以上**（`requires-python = ">=3.11"`） |
| 操作系统 | Windows / macOS / Linux |
| 运行时依赖 | `click`、`pyyaml`、`python-dotenv` |

**这是本框架当前的硬门槛**，由扫描证据加"在下界解释器上实跑全量测试"共同支撑——
见[开发指南的「Python 下界的依据」一节](contributing/development.md)。若要提高门槛，
请先把依据写进那一节（门槛的改动不只改 `pyproject.toml`：工具链 target、`uv.lock`、
CI 矩阵与文档中的门槛声明都要同改，`tests/test_doc_consistency.py` 会检查这一致性）。

> **可选的原生执行扩展另有自己的下界（Python 3.13+）。** 它是可选编译扩展、尚未发布，
> 其下界不抬高主包的门槛；在 3.11／3.12 上尝试安装它会在安装期以显式错误结束，而不是
> "装上但不可用"。

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

仓库里提交了 `uv.lock`，它与 `pyproject.toml` 同源（`uv lock --check` 通过）。安装仍推荐：

```bash
pip install -e ".[dev]"     # 推荐
```

若你偏好 uv，`uv sync --extra dev` 会按同一份锁文件解析依赖。改动依赖后请跑 `uv lock`
重锁，并用 `uv lock --check` 复核。

## 卸载

```bash
pip uninstall zoo-framework
```

框架运行时会在工作目录产生 `zooStates.pic` 与 `backups/`（状态文件与滚动备份）。
卸载不会删除它们，需要自行清理。
