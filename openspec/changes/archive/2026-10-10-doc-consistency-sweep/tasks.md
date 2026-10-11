# doc-consistency-sweep 任务清单

## 1. 文档修复（issue 第 1–5 条）

- [x] 1.1 隐喻表：CLAUDE.md L11-15 表替换为 README.md Core concepts 版（8 行，
      Zookeeper/Food/Feeder 消失）；docs/README.md L170 列举补全 Reactor/StateMachine
      （验证：grep `Zookeeper`、`Food` 在 CLAUDE.md 表区零命中）
- [x] 1.2 SVM 宣称诚实化：docs/ARCHITECTURE.md L86 与 roadmap.md L15 补
      「指标链路尚未接通」标注（验证：grep 两处均带标注）
- [x] 1.3 ELS 背书：roadmap.md L15 / L301-304 区块、internal/business-plan.md L62
      改为可核实表述（验证：对外文档 grep `ELS` 零命中）
- [x] 1.4 Python 门槛：docs/contributing/development.md L11（3.8/3.11 → 3.13）
      与 L355（3.8+ → 3.13+）（验证：grep 该文件无 3.8）
- [x] 1.5 测试数量口径：docs/contributing/structure.md L18/L168 去 367/23 数值，
      改"见 Tests 徽章"（验证：grep 数字零命中）

## 2. 一致性测试（tests/test_doc_consistency.py 扩展）

- [x] 2.1 `TestPublishedClaimsMatchReality`：
      a) structure.md 无硬编码用例数
      b) development.md 最低 Python 版本 == pyproject requires-python；3.8 禁用
      c) 三处隐喻表映射集合一致 + Zookeeper/Food/Feeder 禁用
      d) `SVM monitoring started` 全库零命中；宣称处带「尚未接通」标注
      （验证：4 条测试通过）
- [x] 2.2 牙齿验证（assertion-integrity / bugfix 串行纪律）：对 4 条测试逐条
      注入违规（恢复 367 / 写回 3.8 / 加回 Zookeeper 行 / 删标注），确认变红，
      md5 还原核对（验证：4 次注入均红，还原后源文件逐字节一致）
- [x] 2.3 全量 pytest 全绿（验证：>= 1024 passed）

## 3. 回归与验证

- [x] 3.1 门禁：ruff check / ruff format（仅改动文件）/ mypy（验证：全过）
- [x] 3.2 `openspec validate doc-consistency-sweep --strict` 通过（验证：0 警告）
- [x] 3.3 核对表（proposal 内 10 条处置列）与最终实况一致（验证：人工过一遍）
