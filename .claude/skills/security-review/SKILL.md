---
name: security-review
description: 安全审查 Skill — 审查 Python 变更的不安全反序列化（pickle）、eval/exec、命令注入、路径穿越、敏感信息泄露、子进程与网络面风险，及 Rust 探针的 unsafe/panic 跨界；供 reviewer 在 .py 与 .rs 变更与提交前调用
---

# Security Review — 安全审查

审查 Zoo Framework 的安全风险。reviewer 在审查 `**/*.py` / `**/*.rs` 变更及提交前安全闸门时调用本 skill。bandit 机械扫描（`bandit -r zoo_framework -c .bandit.yaml`）为线索，语义判断由审查完成。

## 机械预扫（工具线索，非结论）

```bash
bandit -r zoo_framework -c .bandit.yaml      # 命中的规则作为必查线索，逐条人工确认
```
**bandit 可承担**（模式匹配类）：不安全反序列化（B301 pickle.load）、`exec`/`eval`（B102/B307）、`subprocess shell=True`（B602）、硬编码密钥/临时目录（B105/B108）、`assert` 滥用（B101）。
**不可委托（人工深审）**：数据信任边界（存档/配置文件内容是否可信来源）、并发引入的 TOCTOU、路径规范化的越权、任何需要 `文件:行号` 精确引用的断言。误报过滤后不输出。

## 审查维度

### 1. 不安全反序列化（本项目重点）
- 状态机存档用 **pickle**（`statemachine/`、`core/persistence_scheduler.py`）：`pickle.load` 可执行任意代码
  - 只加载**受信来源**的存档文件；来源不可控（用户上传/网络获取）→ 🔴，改用带校验和/签名的受信路径，或换 JSON/msgpack 等纯数据格式
  - 加载前是否校验 checksum（本项目有校验和机制）；校验失败必须拒绝加载而非继续
  - `PicklePersistenceStrategy` 反序列化的类型面是否受限（理想用受限 `Unpickler`/白名单）
- 配置 `json.load` 相对安全，但注意路径来源可信

### 2. 代码执行与动态求值
- 禁止对**外部输入**使用 `eval`/`exec`；插件动态加载（`PluginManager.load_from_path`）路径是否受信、是否可被注入
- 禁止 `pickle.loads`/`yaml.load`（不安全 Loader）处理不可信数据

### 3. 命令注入与子进程（utils/cmd_utils.py）
- `subprocess` 调用禁止 `shell=True` 拼接用户/配置输入（B602）；用参数列表形式
- 外部命令参数是否来自可控来源；用户可控值是否转义/校验

### 4. 路径与文件操作（utils/file_utils.py、持久化）
- 路径拼接是否防**目录穿越**（`..`），尤其 CLI 脚手架（`zfc --create`）、插件 `load_from_path`、存档路径 `stateMachine:picklePath` 来自配置时
- 原子写 `os.replace` 的临时文件是否与目标同目录（避免跨设备/竞态）；备份目录权限
- 临时文件是否用受控目录（B108 硬编码 `/tmp`）

### 5. 敏感信息泄露
- 日志/异常是否打印密钥、token、连接串、环境变量敏感值（`.env`）
- 配置中的敏感项是否有环境区分方案（不硬编码进仓库）
- 错误响应/traceback 是否泄露内部路径与实现细节

### 6. 网络与 WebSocket（utils/ws_utils.py）
- 是否禁用证书/主机校验（`verify=False`、`ssl` 降级）→ 🔴
- URL 来源是否可信，是否有 SSRF 面（可配置的目标地址）

### 7. 并发与资源安全
- 守护线程/子进程是否可能残留（资源泄漏→拒绝服务面）
- 锁使用是否有死锁导致的可用性风险（`lock/`、`ThreadSafeDict`）

### 8. Rust 探针（bench/pyo3_probe/）
- `unsafe` 块是否有充分理由与安全注释；裸指针/FFI 边界
- panic 不得跨越到 Python（须 `PyResult`/`catch_unwind`），否则进程崩溃
- 持有 GIL 时不执行长阻塞/不回调 Python 造成死锁

## 输出格式

```
## 安全审查报告

### 风险等级
- 🔴 高危（必须修复）：...
- 🟡 中危（建议修复）：...
- 🔵 低危（注意）：...
- ✅ 通过：...

### 各维度检查
1. 不安全反序列化（pickle）：✅ / 🔴 ...
2. 代码执行与动态求值：✅ ...
3. 命令注入与子进程：✅ ...
4. 路径与文件操作：✅ ...
5. 敏感信息泄露：✅ ...
6. 网络与 WebSocket：✅ ...
7. 并发与资源安全：✅ ...
8. Rust unsafe/panic：✅ / 不涉及

### 详细发现
| 文件:行号 | 风险等级 | 问题描述 | 修复建议 |
|-----------|---------|---------|---------|
```

## 工作约束

- 审查时不修改代码，只输出安全审查报告
- 每个发现必须标注：`文件:行号` + 风险等级 + 问题描述 + 修复代码示例
- 高危问题必须给出可直接替换的安全修复代码
- 不产生误报（不确定的标记"需人工确认"）
