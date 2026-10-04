---
name: cross-platform-review
description: 跨平台一致性审查 Skill — 审查代码在 Windows/Linux/macOS 三平台的行为差异（文件编码显式声明、os.replace 原子性与路径、定时器分辨率、WSL2 唤醒失真、信号与 daemon 线程语义、备份命名唯一性），对应 openspec cross-platform-io 规格；供 reviewer 在 utils/、持久化、调度器、计时相关变更时附加调用
---

# Cross-Platform Review — 跨平台一致性审查

审查代码变更在 Windows / Linux / macOS 上是否行为一致，防止"只在开发机能跑"的缺陷。对应 `openspec/specs/cross-platform-io/spec.md` 与 CI 的三平台矩阵（ubuntu / windows / macos，Python 3.13）。reviewer 在涉及 `zoo_framework/utils/**`、持久化、调度/计时、进程/线程生命周期的变更时附加调用本 skill。

## 触发变更路径
- `zoo_framework/utils/file_utils.py`、`log_utils.py`、`structured_log.py`（编码/路径/控制台输出）
- `zoo_framework/core/persistence_scheduler.py`、`statemachine/**`（`os.replace`、备份命名）
- `zoo_framework/core/waiter/**`、`reactor/event_priorities.py`、计时相关（timer 分辨率、超时）
- `zoo_framework/utils/cmd_utils.py`（子进程、信号）
- `example/config.json` 及任何配置文件读写（编码）

## 审查维度

### 1. 文本编码（cross-platform-io 核心）
- 文本文件写入 MUST 显式声明 `encoding="utf-8"`，禁止依赖平台默认编码（Windows 默认 GBK/cp936 会产生平台相关字节）
- 读取 MUST 优先按 UTF-8 解码；回退到平台默认编码时 MUST 输出可观测告警，**禁止静默回退**
- 日志输出 MUST NOT 因控制台不支持某字符而整行丢失（不可表示字符降级写出、保留码位可还原）
- 违反判断：`open()` 无 `encoding=`、配置文件读写依赖 locale、日志遇非 ASCII 抛异常丢行 → 🔴

### 2. 文件路径与原子替换
- 路径拼接用 `os.path.join` / `pathlib`，禁止手写 `"/"`、`"\\"` 分隔符
- `os.replace` 原子性：临时文件必须与目标**同目录同文件系统**（跨卷 `os.replace` 非原子，Windows 尤其）
- 存档/备份路径来自配置时校验合法性（见 security-review 路径穿越）
- 违反判断：跨卷 rename 假设原子、硬编码分隔符 → 🔴/🟡

### 3. 备份命名唯一性与可排序（cross-platform-io）
- 同一秒内连续备份 MUST 产生互不覆盖的唯一文件名（本项目用微秒后缀，如 `state_machine_{ts}_{us}.pkl`）
- 备份文件名 MUST 满足"字典序 == 时间序"（零填充，不用会乱序的格式）
- 新旧命名混排时取"最新"逻辑仍正确

### 4. 定时器与超时分辨率
- 平台 timer 分辨率不同（bench/measure_timer 已实测：Windows 默认约 15.6ms 粒度，Linux 更细），依赖 `time.sleep(1)` 轮询/超时的语义在两平台误差不同
- `EventParams.EVENT_JOIN_TIMEOUT`、`delay_time`、状态机 5s 循环等对精度敏感处，审查是否容忍平台误差，是否用 `time.monotonic()`（不受系统时钟调整影响）而非 `time.time()`

### 5. 线程/进程与信号语义
- 守护线程（daemon）退出行为跨平台一致；`zoo_thread` 是否依赖特定平台线程语义
- `KeyboardInterrupt` 捕获（`Master.run` 循环退出）在非 Windows 终端信号（SIGINT）下的一致性
- 子进程/`multiprocessing.Lock` 在 Windows 无 `fork`（spawn 启动开销大），bench 已测 `multiprocessing.Lock` 慢于 `threading.RLock`——锁选型见 architecture-review

### 6. CI 三平台矩阵
- 新增测试/功能是否在 ubuntu/windows/macos 都能通过（CI 强制三平台 Python 3.13）
- 平台特定断言是否用 `sys.platform` / `platform.system()` 守卫，避免只在单机通过
- 注意工作树里 3.9 的 `venv/` 无法导入本包——本地验证须用 3.13 解释器（`uv run --no-sync` / `.venv`）

## 执行流程

### Step 1: 识别平台敏感变更
```bash
git diff main...HEAD --name-only
```
命中上述触发路径 → 进入对应维度审查。

### Step 2: 逐维度核查
按 1-6 维度检查，每条发现给 `文件:行号` + 违反的 cross-platform-io Requirement（若对应）+ 平台差异说明 + 修复建议。

### Step 3: 输出报告
```
## 跨平台一致性审查报告
### 编码：✅ / 🔴 ...
### 路径与原子替换：✅ / 🟡 ...
### 备份命名：✅ ...
### 计时分辨率：✅ / 🔵 ...
### 线程/信号语义：✅ ...
### CI 三平台：✅ / ⚠️ 需补平台守卫 ...
### 结论：✅ 通过 / ⚠️ 建议 / ❌ 阻断
```

## 工作约束
- 只审查不修改代码，只输出报告
- 每个发现标注 `文件:行号` + 平台差异 + 违反的 cross-platform-io 条款
- 性能相关读数须引用 bench 实测（WSL2 数据不可用，见 perf-guardian）
- 不确定的平台行为标记"需人工确认"或建议"在 CI 三平台验证"
- 与 persistence-review 分工：本 skill 管跨平台行为差异，持久化格式/校验/兼容细节归 persistence-review
