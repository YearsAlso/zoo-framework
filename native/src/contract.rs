//! 契约握手与三族错误到 Python 异常的映射.
//!
//! 扩展侧上报的常量（`contract_version()` / `capabilities()` / `tasks()`）与
//! Python 侧 `zoo_framework.native.contract` 的约定逐字对齐：
//! - `contract_version()` MUST 等于框架的 `CONTRACT_VERSION`（主版本不匹配即拒绝）
//! - `capabilities()` MUST NOT 声明适配器不支持的能力（internal_parallel / zero_copy）
//! - `tasks()` 的值 MUST 是框架侧 `NativeTaskContract` 的真实实例——适配器按
//!   属性访问读取字段，dict 会在执行路径上炸
//! - `execute()` 失败 MUST 抛三族异常实例；抛其它异常会被适配器兜成
//!   `NativePanic`（那是 panic 族的语义，不该承载受控业务失败）

use pyo3::prelude::*;
use pyo3::types::PyType;

use crate::modbus::TaskError;

/// 与 zoo_framework/native/contract.py 的 `CONTRACT_VERSION` 保持一致.
pub const CONTRACT_VERSION: u32 = 1;

/// 首个真实任务（native/DECISION.md 阶段 0 选定：Modbus RTU 响应帧解析）.
pub const TASK_MODBUS_RTU_PARSE_RESPONSE: &str = "modbus_rtu.parse_response";

/// 任务契约声明的输入上限 = RTU ADU 字节上限.
pub const TASK_MODBUS_MAX_INPUT_BYTES: i64 = 256;

/// 把 Rust 侧受控错误映射为 Python 三族异常实例.
///
/// 异常类从框架契约模块按名取（执行时 import 有模块缓存，成本一次 dict 查找）；
/// 契约模块不可达（扩展被脱离框架独立使用）时退回 RuntimeError 并携带族名前缀，
/// 不静默吞掉分类信息。
pub fn into_py_err(py: Python<'_>, err: TaskError) -> PyErr {
    let (class_name, message) = match err {
        TaskError::InvalidInput(msg) => ("NativeInvalidInput", msg),
        TaskError::TaskFailed(msg) => ("NativeTaskFailed", msg),
    };

    let resolved = py
        .import("zoo_framework.native.contract")
        .ok()
        .and_then(|m| m.getattr(class_name).ok())
        .and_then(|c| c.downcast_into::<PyType>().ok());
    if let Some(exc_class) = resolved {
        PyErr::from_type(exc_class, (message,))
    } else {
        pyo3::exceptions::PyRuntimeError::new_err(format!("[{class_name}] {message}"))
    }
}

/// 构造 Modbus RTU 任务的契约描述（框架侧 NativeTaskContract 的真实实例）.
pub fn build_modbus_contract(py: Python<'_>) -> PyResult<Py<PyAny>> {
    let module = py.import("zoo_framework.native.contract")?;
    let cls = module.getattr("NativeTaskContract")?;
    // 位置实参顺序 = NativeTaskContract 字段序：
    // name, contract_version, input_format, max_input_bytes, output_format,
    // error_classes, capabilities
    let args = (
        TASK_MODBUS_RTU_PARSE_RESPONSE,
        CONTRACT_VERSION as i64,
        "bytes",
        TASK_MODBUS_MAX_INPUT_BYTES,
        "json",
        ("NativeInvalidInput", "NativeTaskFailed"),
        pyo3::types::PyTuple::empty(py),
    );
    Ok(cls.call1(args)?.unbind())
}
