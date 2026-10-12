//! 最小原生任务模板（issue #139）——契约的可编译范例.
//!
//! 完整契约说明见 `docs/native-tasks.md`。四条纪律（与 `native/src/lib.rs` 同）：
//!
//! 1. `contract_version()` MUST 等于框架的 `CONTRACT_VERSION`；主版本不匹配时适配器拒绝加载。
//! 2. `capabilities()` MUST NOT 声明适配器不支持的能力（`internal_parallel` / `zero_copy`）。
//! 3. `tasks()` 的值 MUST 是框架侧 `NativeTaskContract` 的真实实例——适配器按属性访问读字段。
//! 4. `execute()` MUST 用三族异常上报失败；抛其它异常会被适配器兜成 `NativePanic`。
//!
//! 另两条执行纪律：执行期间用 `py.detach(..)` 离开解释器（GIL 释放是多核伸缩的前提）；
//! 执行体 MUST NOT 回调 Python（粗粒度任务，一次跨界完成全部工作）。

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

/// 与 `zoo_framework/native/contract.py` 的 `CONTRACT_VERSION` 一致.
const CONTRACT_VERSION: u32 = 1;
/// 任务名由你决定；框架侧只按名字分派，不认识业务语义.
const TASK_NAME: &str = "example.sum_bytes";
/// 声明的输入上限：适配器在**进入执行体之前**按它拒绝超限输入.
const MAX_INPUT_BYTES: i64 = 4096;

/// 受控错误的两族（第三族是 panic，由 PyO3 在 FFI 边界处理）.
#[derive(Debug)]
enum TaskError {
    /// 任务根本没开始跑（长度、结构等结构性拒绝）.
    InvalidInput(String),
    /// 任务跑了并给出受控业务结论.
    TaskFailed(String),
}

/// 示例执行体：字节和 + 计数。纯逻辑、不接触 Python，故可被 `cargo test` 直接覆盖.
fn sum_bytes(payload: &[u8]) -> Result<(u64, u64), TaskError> {
    if payload.is_empty() {
        return Err(TaskError::InvalidInput("输入为空".to_string()));
    }
    let mut sum: u64 = 0;
    for byte in payload {
        sum += u64::from(*byte);
    }
    Ok((payload.len() as u64, sum))
}

/// 把受控错误映射为框架侧三族异常实例；契约模块不可达时退回 RuntimeError
/// 并保留族名前缀，不静默吞掉分类信息.
fn into_py_err(py: Python<'_>, err: TaskError) -> PyErr {
    let (class_name, message) = match err {
        TaskError::InvalidInput(msg) => ("NativeInvalidInput", msg),
        TaskError::TaskFailed(msg) => ("NativeTaskFailed", msg),
    };
    let resolved = py
        .import("zoo_framework.native.contract")
        .ok()
        .and_then(|m| m.getattr(class_name).ok())
        .and_then(|c| c.cast_into::<pyo3::types::PyType>().ok());
    if let Some(exc_class) = resolved {
        PyErr::from_type(exc_class, (message,))
    } else {
        pyo3::exceptions::PyRuntimeError::new_err(format!("[{class_name}] {message}"))
    }
}

#[pyfunction]
fn contract_version() -> u32 {
    CONTRACT_VERSION
}

/// 首版不声明任何能力——**不声明未实现的能力**是契约纪律.
#[pyfunction]
fn capabilities() -> Vec<&'static str> {
    Vec::new()
}

#[pyfunction]
fn tasks(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let registry = PyDict::new(py);
    let contract_cls = py
        .import("zoo_framework.native.contract")?
        .getattr("NativeTaskContract")?;
    // 位置实参顺序 = NativeTaskContract 字段序：
    // name, contract_version, input_format, max_input_bytes, output_format,
    // error_classes, capabilities
    let contract = contract_cls.call1((
        TASK_NAME,
        CONTRACT_VERSION as i64,
        "bytes",
        MAX_INPUT_BYTES,
        "json",
        ("NativeInvalidInput", "NativeTaskFailed"),
        PyTuple::empty(py),
    ))?;
    registry.set_item(TASK_NAME, contract)?;
    Ok(registry)
}

#[pyfunction]
fn execute(py: Python<'_>, task: &str, payload: &[u8]) -> PyResult<Vec<u8>> {
    if task != TASK_NAME {
        return Err(into_py_err(
            py,
            TaskError::InvalidInput(format!("未注册任务 {task:?}")),
        ));
    }
    // detach：执行期间离开解释器（0.25 起 allow_threads 的新名字）
    let result = py.detach(|| sum_bytes(payload));
    match result {
        Ok((count, sum)) => Ok(format!("{{\"count\": {count}, \"sum\": {sum}}}").into_bytes()),
        Err(err) => Err(into_py_err(py, err)),
    }
}

#[pymodule]
fn example_native_task(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(contract_version, m)?)?;
    m.add_function(wrap_pyfunction!(capabilities, m)?)?;
    m.add_function(wrap_pyfunction!(tasks, m)?)?;
    m.add_function(wrap_pyfunction!(execute, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sums_and_counts() {
        assert_eq!(sum_bytes(&[1, 2, 3]).unwrap(), (3, 6));
    }

    #[test]
    fn empty_input_is_invalid_input() {
        match sum_bytes(&[]) {
            Err(TaskError::InvalidInput(_)) => {}
            _ => panic!("空输入必须是 InvalidInput"),
        }
    }

    #[test]
    fn contract_version_is_one() {
        assert_eq!(contract_version(), 1);
    }
}
