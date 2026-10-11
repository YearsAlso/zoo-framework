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
- [ ] 3.4 **发布链路的真实验证只能等下一个 tag**：本变更触及 `release.yml`，合入后会触发
      一次版本号 PR；其合并产生的 tag 才会跑完 `Generate Changelog` → `Create GitHub
      Release`。在那之前不得声称发布链路已恢复
- [ ] 3.5 遗留（本变更不做，需人工决定）：`v0.12.0` 已上传 PyPI 但没有 GitHub Release——
      是否回填 `CHANGELOG.md` 的 0.12.0 段、是否补建该 Release，属发布记录本身
