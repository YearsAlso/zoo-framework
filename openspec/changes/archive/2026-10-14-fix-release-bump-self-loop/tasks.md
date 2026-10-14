# tasks — fix-release-bump-self-loop

## 1. 规格（spec-first）

- [x] 1.1 `specs/ci-and-packaging/spec.md` 写入 MODIFIED Requirement：自环防护条款 + 场景
      「版本号提交不自环」，并把陈旧的"仅三处版本声明"改为"版本声明"
- [x] 1.2 `openspec validate fix-release-bump-self-loop --strict` 通过

## 2. 实现

- [x] 2.1 `release.yml` 的 `ONLY_VERSION` 白名单补 `CITATION.cff`（四处与 bump 步骤逐项
      一致），注释写明维护约束与失效后果
- [x] 2.2 `release.yml` 的声明回声检测 `git diff origin/main HEAD --` 比较清单同样补齐
      四处（同一根因的第二处漏列），`echo` 文案"三处"→"四处"

## 3. 机械校验

- [x] 3.1 `tests/test_doc_consistency.py` 新增
      `test_release_tag_decision_covers_every_version_place`：解析出"版本声明处"集合，
      断言白名单与回声清单**都等于它**（漏列与多列都红）
- [x] 3.2 配套 `test_tag_decision_scanner_has_teeth`：正反样本自检，防解析漂移成空跑
- [x] 3.3 断言"有牙齿"：注入违规（白名单删 `CITATION.cff` / 回声清单删 `CITATION.cff`）
      逐个确认变红，再按 md5 逐字节还原
- [x] 3.4 `pytest tests/test_doc_consistency.py -k "version_place or bump_covers or
      tag_decision"` → 4 passed（含既有的 `test_release_bump_covers_every_version_place`
      与 `test_release_sed_patterns_match_their_files`，确认未破坏既有校验）

## 4. 验证边界

- [x] 4.1 如实记录：**自环是否真的停止，只能由合入后的下一次 bump 合并证明**——本变更
      无法在 PR 内触发一次真实的 bump/tag 判定；不得声称"已修复自环"
- [x] 4.2 记录收敛路径：本次改动触及 `release.yml`（相关性白名单内）→ 合入后仍会开出一个
      bump PR；合并它时四处清单一致 → 判定 `tag` → 自环终止，dev 首次打出 tag
