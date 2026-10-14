## 1. 反向护栏先行

- [x] 1.1 在改动任何代码之前，先跑既有构造契约的护栏用例
      `python -m pytest tests/test_runtime_defects.py::TestFrameworkEntrypoint -q`，
      记录基线为全绿（尤其 `test_master_construction_is_repeatable`）——
      这是后续所有改动的对照基准，缺了它无法证明本变更没误伤既有契约
- [x] 1.2 跑一次全量 `python -m pytest -q`，记录通过数与耗时作为本树基线
      （本树无未跟踪的 `docs/docs/` 与 `node_modules/`，预期全绿）

## 2. 运行态登记（D2）

- [x] 2.1 在容器内新增"进程内运行态管理器"的登记与查询接缝：登记 MUST 经容器的进程级作用域持有，
      且 `framework_container().reset()` 能使其清空；验证方式：新增用例断言
      `reset()` 后"是否已有运行态管理器"回到初始态
- [x] 2.2 为 2.1 的接缝加资源释放语义（管理器停机时清除登记），
      验证方式：用例覆盖"置位 → 清除 → 再次可置位"的完整往返

## 3. 运行态唯一性判定（D1、D4）

- [x] 3.1 在框架管理器进入运行态的入口加唯一性判定：已有运行态管理器时抛出异常且不产生派发；
      验证方式：用例先让一个管理器进入运行态，再尝试第二个，断言抛异常
- [x] 3.2 登记的清必须走 `try/finally`：运行过程抛异常时登记也要清除；
      验证方式：用例让运行过程抛出受控异常，断言此后另一个管理器仍能正常进入运行态
      （对应 design 的「假的活跃标记」风险）
- [x] 3.3 确认构造但未运行的管理器**不占用**唯一性额度；
      验证方式：`test_master_construction_is_repeatable` 保持绿，且新增用例覆盖
      "同进程先后构造多个管理器均成功"

## 4. 构造期早期识别（D3）

- [x] 4.1 在框架管理器构造的早期（解析任何进程级共享对象之前）识别"本进程已有管理器且当前线程不同"，
      抛出同一边界语义的错误；验证方式：用例在两个线程上先后构造管理器，
      断言错误信息包含"同进程"而非仅含内部注册项名
- [x] 4.2 回归：确认跨线程构造的报错**不再**以容器内部注册项名作为首要信息，
      验证方式：读该用例捕获到的错误文本并断言其不含内部注册项全限定名
- [x] 4.3 确认容器对 `SINGLE_THREAD` 的通用拒绝语义**未被改动**，
      验证方式：跑 `python -m pytest tests/test_scoped_container.py -q`（若文件名不同则按实际）保持绿

## 5. 文档（D5）

- [x] 5.1 在 `docs/ARCHITECTURE.md` 的容器一节补写"一个进程一个运行态管理器"的边界与原因，
      验证方式：该节包含边界描述与原因，且措辞与实现一致
- [x] 5.2 在 `docs/FAQ.md` 新增一节，给出受支持的替代形态（独立进程；进程池 + 事件回传）
      及各自适用条件，验证方式：能查到替代形态且不含"支持同进程嵌套"的表述
- [x] 5.3 确认文档未夸大支持范围（spec 的「文档不夸大支持范围」场景），
      验证方式：`python -m pytest tests/test_doc_consistency.py -q` 保持绿，
      并人工核对新增段落不出现同进程嵌套可用的暗示

## 6. 收口验证

- [x] 6.1 全量 `python -m pytest -q` 与基线（1.2）逐项比对，通过数不少于基线且无新增失败
- [x] 6.2 `ruff check zoo_framework`、`ruff format --check zoo_framework`、`mypy zoo_framework` 三项门禁全过
- [x] 6.3 `openspec validate document-nested-master-boundary --strict` 通过
- [x] 6.4 在 issue #248 下留完成回调（2026-10-14，
      https://github.com/YearsAlso/zoo-framework/issues/248#issuecomment-6168511377）：
      逐条对照其验收标准，含「构造期报错」更正为「第二个 Master 启动时拒绝」的必要前提更正，
      并给出 `zoo-code-agent#43` 可引用的文档段落定位 —— `docs/ARCHITECTURE.md` 的
      **作用域容器**一节末尾（边界与原因）、`docs/FAQ.md` 的「一个进程能跑多个运行时吗？」
      （替代形态与适用条件）。对应 PR #252
