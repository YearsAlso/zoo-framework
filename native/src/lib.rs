//! zoo_framework_native — zoo-framework 原生任务执行扩展（契约版本 1）.
//!
//! 形状（add-native-task-execution design D2/D3）：
//! - Python 保留编排与生命周期；本扩展只承载**任务执行体**，执行期间用
//!   `py.allow_threads` 释放 GIL（真多核伸缩的机制前提，实测见 native/DECISION.md）。
//! - 执行体不回调 Python：粗粒度原生任务，一次跨界完成全部工作（跨界成本
//!   28.9ns，可忽略；收益稀释主因是任务边界而非 GIL 往返）。
//! - panic = unwind：PyO3 在 FFI 边界把 panic 转为 PanicException，适配器兜底
//!   映射为 `NativePanic`——MUST NOT abort 进程。
//!
//! 对 Python 适配器（zoo_framework/native/adapter.py）暴露的四个入口：
//!   contract_version() / capabilities() / tasks() / execute(task, payload)
//! 语义细节见 contract.rs 模块注释。

mod contract;
mod modbus;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::contract::{
    build_modbus_contract, into_py_err, TASK_MODBUS_RTU_PARSE_RESPONSE, CONTRACT_VERSION,
};
use crate::modbus::TaskError;

/// 上报执行契约版本（适配器与框架 `CONTRACT_VERSION` 比对）.
#[pyfunction]
fn contract_version() -> u32 {
    CONTRACT_VERSION
}

/// 上报扩展整体能力清单（首版为空——不声明未实现的能力）.
#[pyfunction]
fn capabilities() -> Vec<&'static str> {
    Vec::new()
}

/// 上报任务注册表：任务名 -> 框架侧 NativeTaskContract 实例.
#[pyfunction]
fn tasks(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let registry = PyDict::new(py);
    registry.set_item(TASK_MODBUS_RTU_PARSE_RESPONSE, build_modbus_contract(py)?)?;
    Ok(registry)
}

/// 执行一个原生任务：输入字节 -> 执行体（期间释放 GIL）-> JSON 字节输出.
///
/// 错误语义：
/// - 未注册任务名 / 结构性输入问题 → `NativeInvalidInput`
/// - 受控业务失败（CRC 不符 / 功能码不支持 / 帧结构不一致）→ `NativeTaskFailed`
/// - unwind panic → PyO3 PanicException，适配器兜 `NativePanic`
#[pyfunction]
fn execute(py: Python<'_>, task: &str, payload: &[u8]) -> PyResult<Vec<u8>> {
    match task {
        TASK_MODBUS_RTU_PARSE_RESPONSE => {
            let result = py.allow_threads(|| modbus::parse_response(payload));
            match result {
                Ok(parsed) => Ok(parsed.to_json()),
                Err(err) => Err(into_py_err(py, err)),
            }
        }
        other => Err(into_py_err(
            py,
            TaskError::InvalidInput(format!("原生扩展未注册任务 {other:?}")),
        )),
    }
}

#[pymodule]
fn zoo_framework_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(contract_version, m)?)?;
    m.add_function(wrap_pyfunction!(capabilities, m)?)?;
    m.add_function(wrap_pyfunction!(tasks, m)?)?;
    m.add_function(wrap_pyfunction!(execute, m)?)?;
    Ok(())
}
