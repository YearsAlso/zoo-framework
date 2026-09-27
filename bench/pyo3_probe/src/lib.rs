//! PyO3 边界成本探针.
//!
//! 只用于测量（对应 adopt-rust-core 的任务组 2/3/4），不进入产品代码。
//! 测量的三件事：
//!   1. Python -> Rust 的调用往返成本
//!   2. Rust -> Python 的回调成本（持有 GIL）
//!   3. Python::allow_threads 释放并重新获取 GIL 的往返成本
//! 外加一条必然 panic 的路径，用于验证崩溃隔离（design D3）。

use std::hint::black_box;
use std::panic;

use pyo3::prelude::*;

/// Python -> Rust 的空调用往返.
#[pyfunction]
fn noop() {}

/// Rust -> Python 的回调（持有 GIL 调用一个 Python 可调用对象）.
#[pyfunction]
fn call_python(py: Python<'_>, callable: Py<PyAny>) -> PyResult<()> {
    callable.call0(py)?;
    Ok(())
}

/// 释放并重新获取 GIL 的往返成本.
#[pyfunction]
fn allow_threads_roundtrip(py: Python<'_>) {
    py.allow_threads(|| {});
}

/// 细粒度形态：N 次跨界调用，每次只调用一次 Python 回调.
#[pyfunction]
fn fine_grained(py: Python<'_>, n: usize, callable: Py<PyAny>) -> PyResult<()> {
    for _ in 0..n {
        callable.call0(py)?;
    }
    Ok(())
}

/// 粗粒度形态：Rust 侧独立完成 N 件事（期间释放 GIL），只穿越一次边界.
///
/// 与 `fine_grained` 的比值即 design D2「粗粒度调用」约束的数据依据。
/// 循环体内用 `black_box` 阻止编译器把整段工作优化掉——否则测出的"Rust 侧工作成本"
/// 会趋近于零，比值失去意义。
#[pyfunction]
fn coarse_grained(py: Python<'_>, n: usize, callable: Py<PyAny>) -> PyResult<()> {
    py.allow_threads(|| {
        let mut acc: u64 = 0;
        for i in 0..n as u64 {
            let term = black_box(i).wrapping_mul(black_box(i.wrapping_add(1)));
            acc = black_box(acc.wrapping_add(term));
        }
        black_box(acc);
    });
    callable.call0(py)?;
    Ok(())
}

/// 必然 panic、且**不**兜住的路径.
///
/// 用于验证 PyO3 是否把 panic 转换为 Python 异常而非让整个进程 abort.
#[pyfunction]
fn panics() {
    panic!("probe: intentional panic");
}

/// 在 FFI 边界处兜住 panic，转换为 Python 异常.
#[pyfunction]
fn catches_panic() -> PyResult<()> {
    let result = panic::catch_unwind(|| {
        panic!("probe: caught panic");
    });

    match result {
        Ok(()) => Ok(()),
        Err(payload) => {
            let message = payload
                .downcast_ref::<&str>()
                .map(|s| (*s).to_string())
                .or_else(|| payload.downcast_ref::<String>().cloned())
                .unwrap_or_else(|| "unknown panic payload".to_string());
            Err(pyo3::exceptions::PyRuntimeError::new_err(message))
        }
    }
}

/// 在持有 Python 引用期间 panic，验证不出现悬垂引用.
#[pyfunction]
fn panics_holding_python_ref(py: Python<'_>, callable: Py<PyAny>) -> PyResult<()> {
    let held = callable.clone_ref(py);
    black_box(&held);
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        panic!("probe: panic while holding a python reference");
    }));
    match result {
        Ok(()) => Ok(()),
        Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err("caught")),
    }
}

/// 最小 Tokio 调度器：Rust 持有线程池，每次任务只穿越一次边界执行 Python 执行体.
///
/// 用于与 Python 侧的调度路径做同机对照（adopt-rust-core 任务组 5）。
/// 它**不**实现完整的调度语义（无超时熔断、无在飞表、无结果聚合）——对照的是
/// "把一段 Python 执行体派发出去并收到完成信号"这条路径的成本。
#[pyclass]
struct RustDispatcher {
    runtime: Option<tokio::runtime::Runtime>,
    completion: Py<PyAny>,
}

#[pymethods]
impl RustDispatcher {
    #[new]
    fn new(workers: usize, completion: Py<PyAny>) -> PyResult<Self> {
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(workers)
            .enable_time()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(Self {
            runtime: Some(runtime),
            completion,
        })
    }

    /// 把一个 Python 可调用对象提交到 Rust 线程池.
    ///
    /// 任务体与完成回调各穿越一次边界。
    fn submit(&self, py: Python<'_>, task: Py<PyAny>) -> PyResult<()> {
        let task = task.clone_ref(py);
        let completion = self.completion.clone_ref(py);

        let runtime = self
            .runtime
            .as_ref()
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("dispatcher 已停机"))?;

        runtime.spawn(async move {
            Python::with_gil(|py| {
                let _ = task.call0(py);
            });
            Python::with_gil(|py| {
                let _ = completion.call0(py);
            });
        });

        Ok(())
    }

    /// 停机：等待在飞任务结束.
    fn shutdown(&mut self, py: Python<'_>) {
        // shutdown_timeout 会消费 Runtime，因此从 Option 中取出
        if let Some(runtime) = self.runtime.take() {
            py.allow_threads(|| {
                runtime.shutdown_timeout(std::time::Duration::from_secs(5));
            });
        }
    }
}

#[pymodule]
fn pyo3_probe(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(noop, m)?)?;
    m.add_function(wrap_pyfunction!(call_python, m)?)?;
    m.add_function(wrap_pyfunction!(allow_threads_roundtrip, m)?)?;
    m.add_function(wrap_pyfunction!(fine_grained, m)?)?;
    m.add_function(wrap_pyfunction!(coarse_grained, m)?)?;
    m.add_function(wrap_pyfunction!(panics, m)?)?;
    m.add_function(wrap_pyfunction!(catches_panic, m)?)?;
    m.add_function(wrap_pyfunction!(panics_holding_python_ref, m)?)?;
    m.add_class::<RustDispatcher>()?;
    Ok(())
}
