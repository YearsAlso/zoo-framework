# packaging-standards 任务清单

## 1. PEP 639 许可证迁移（issue #119 第 1 条）

- [x] 1.1 `pyproject.toml`：`license = "Apache-2.0"` + `license-files = ["LICENSE"]`；
      `[build-system].requires` 设 hatchling 最低版本下限
      （验证：构建产物 `METADATA` 含 `License-Expression` 与 `License-File`；
      下限值以实测回写 design D1）
- [x] 1.2 删除 `License :: OSI Approved :: Apache Software License` classifier
      （验证：`classifiers` 无 `License ::` 条目；REPO_METADATA 的必须清单未受影响）

## 2. 元数据完整性取舍（issue #119 第 2 条）

- [x] 2.1 按 design D4 逐项核对 readme content-type / keywords / classifiers /
      project.urls / optional-dependencies，只做必要改动
      （验证：与 `docs/REPO_METADATA.md` 投影区逐项比对结论留痕）

## 3. CITATION.cff（issue #119 第 3 条）

- [x] 3.1 新增根目录 `CITATION.cff`（CFF 1.2.0，含 authors/title/version/license/
      repository-code/abstract，值取自 pyproject/README/LICENSE 真源）
      （验证：YAML 可解析 + 六字段齐全 + version 等于 pyproject 版本）
- [x] 3.2 校验：`cffconvert --validate` 通过（schema 1.2.0）——走工具校验，未降级
      （验证：校验结论进变更记录，不谎称已过工具校验）
- [x] 3.3 release.yml「Update version declarations」从三处扩到四处（含 CITATION.cff），
      断言循环同步扩展
      （验证：sed 键匹配写法与既有一致；缺一处即步骤失败）

## 4. SBOM（issue #119 第 4 条，方案 A）

- [x] 4.1 release.yml 在构建后、签名前插入 SBOM 步骤（anchore/sbom-action，
      按 SHA 固定，输出 `dist/*.spdx.json`），失败即工作流失败
      （验证：步骤无 `continue-on-error`；yaml 语法合法）
- [x] 4.2 release 附件 `files:` 列表加入 SBOM 文件
      （验证：列表含 SBOM 且既有 wheel/sdist/sig/pem 未被移除）
- [x] 4.3 不碰签名（cosign）、PyPI OIDC 上传、tag 与版本算术
      （验证：`git diff` 范围仅限上述步骤）

## 5. 真实验证与回归（issue #119 第 5 条）

- [x] 5.1 `python -m build`：sdist + wheel 产出，退出码 0；隔离环境解析 hatchling==1.32.4（实测输出留痕）
- [x] 5.2 `twine check dist/*`：wheel 与 sdist 均 PASSED（留原始输出）
- [x] 5.3 干净环境（uv venv + wheel 安装）→ `import zoo_framework` 输出 0.10.6-beta、`zfc --help` 正常（留原始输出）
- [x] 5.4 门禁：ruff / mypy / 全量 pytest 不回归（留输出）
- [x] 5.5 `openspec validate packaging-standards --strict` 0 警告；tasks 全勾；
      提交（`Closes #119`）+ md5 核对
