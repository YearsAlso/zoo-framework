# tasks — fix-release-notes-heredoc

## 1. 规格（spec-first）

- [x] 1.1 `specs/changelog-backfill/spec.md` 写入 MODIFIED Requirement「release 正文 SHALL 有
      固定四段模板并由 CHANGELOG 驱动」：补「写入 `$GITHUB_OUTPUT` 前 MUST 以换行结尾」与
      Scenario「提交数少的版本仍建出 Release」
- [x] 1.2 `openspec validate fix-release-notes-heredoc --strict` 通过

## 2. 实现

- [x] 2.1 `release.yml` 的 `Generate Changelog` 步骤：多行输出前缀 `printf '\n' >>
      release_notes.md`
- [x] 2.2 该步骤注释写明根因与实测证据（v0.12.0 的 `Invalid value. Matching delimiter not
      found 'EOF'`；`head -20` 只在真截断时补换行，故提交数 < 21 的区间必现）
- [x] 2.3 补机械校验：`tests/test_doc_consistency.py` 新增
      `test_release_notes_are_written_with_a_newline_terminated_payload` + 步骤提取辅助
      `_release_step_run_block`——真的执行该步骤的 `run` 块（`git` / `python` 打桩），
      断言 `$GITHUB_OUTPUT` 可被多行语法解析、正文行未丢

## 3. 验证

- [x] 3.1 `pytest tests/test_doc_consistency.py -q -k release` → 4 passed
- [x] 3.2 用例"有牙齿"：删掉 `printf` 行（修复前的线上状态）→ 变红，失败输出直接显示
      `'- fix(zfc): fake commit (abc1234)EOF'`；按 md5 逐字节还原
      （`release.yml` md5=`d29f1166aaea3e50e6724c80821ef88b`，`md5sum -c` 复核对齐）
- [x] 3.3 单行区间可复现原故障：本机 `git log v0.11.13-beta..v0.12.0 --pretty=format:... |
      head -20` 产出的文件 127 字节、末字节为 `)`；而 0.11.13-beta 的区间（21+ 提交）因
      `head` 截断而带尾换行——两次发布结果不同由此解释
- [x] 3.4 发布链路实测（归档时补记，2026-10-14）：合入后依次产生 `v0.13.0` /
      `v0.13.1-beta` / `v0.13.2-beta` / `v0.14.0` 四个 tag，均跑完
      `Generate Changelog` → `Create GitHub Release`。核验方式
      `gh release list --limit 8`：四条 Release 全部存在、均为已发布状态（非 draft）。
      `gh release view v0.14.0` 正文非空且结构完整（标题 `## 🎉 Release v0.14.0` +
      类型 / 版本 / 「使用者可见的变化」段），末字节截断症状不复现 → 发布链路已恢复
- [x] 3.5 `v0.12.0` 的 Release 已补建（2026-10-11T13:49:40Z，
      https://github.com/YearsAlso/zoo-framework/releases/tag/v0.12.0）：该 tag 此前
      只在 PyPI 上有产物、GitHub 侧无 Release，归档时核对 `gh release list` 已存在。
      本变更不做此事的约定不因此改变，仅记录遗留项已被人工关闭
