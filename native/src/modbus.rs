//! Modbus RTU 响应帧解析——首个原生任务的执行体（阶段 0 选定，见 native/DECISION.md）.
//!
//! 首版范围：
//! - 功能码 0x03 / 0x04 的正常响应帧（读保持 / 输入寄存器）
//! - 异常响应帧（0x83 / 0x84，携带设备侧异常码——**解析成功**，异常语义交调用方解释）
//! - CRC16-MODBUS 校验（反射多项式 0xA001，初值 0xFFFF，线上小端存放）
//!
//! 错误分类（与 Python 侧 `NativeTaskContract.error_classes` 声明对齐）：
//! - `InvalidInput`：结构上无法开始解析（长度 < 4，连 地址+功能码+CRC 都放不下）。
//!   非 bytes 输入由 PyO3 类型提取在进入本函数之前拒绝。
//! - `TaskFailed`：解析已开始后的受控业务失败——CRC 不符 / 功能码不支持 /
//!   帧结构不一致。线上字节损坏是业务现实（干扰、半包），任务确定性给出结论，
//!   不是调用方的输入格式错误。
//!
//! 本模块不依赖 pyo3：纯字节逻辑 + 单元测试独立于 Python 可跑（`cargo test`）。

/// CRC-16/MODBUS 的标准校验值：ASCII "123456789" 的期望 CRC（独立已知答案）。
pub const CRC_CHECK_VALUE: u16 = 0x4B37;

/// RTU ADU 的字节上限（地址 1 + 功能码 1 + 数据 253 + CRC 2）。
pub const MAX_ADU_LEN: usize = 256;

const fn build_crc_table() -> [u16; 256] {
    let mut table = [0u16; 256];
    let mut i = 0usize;
    while i < 256 {
        let mut crc = i as u16;
        let mut bit = 0;
        while bit < 8 {
            crc = if crc & 1 != 0 { (crc >> 1) ^ 0xA001 } else { crc >> 1 };
            bit += 1;
        }
        table[i] = crc;
        i += 1;
    }
    table
}

/// 查表法 CRC-16/MODBUS（初值 0xFFFF，输入不取反、输出不取反）。
static CRC_TABLE: [u16; 256] = build_crc_table();

pub fn crc16_modbus(data: &[u8]) -> u16 {
    let mut crc: u16 = 0xFFFF;
    for &byte in data {
        let idx = ((crc ^ byte as u16) & 0xFF) as usize;
        crc = (crc >> 8) ^ CRC_TABLE[idx];
    }
    crc
}

/// 解析失败的受控错误分类（三族中前两族的数据形态；panic 族由边界兜底承担）。
#[derive(Debug, PartialEq, Eq)]
pub enum TaskError {
    /// 对应 Python 侧 `NativeInvalidInput`：任务根本没开始跑。
    InvalidInput(String),
    /// 对应 Python 侧 `NativeTaskFailed`：任务跑了并给出受控业务结论。
    TaskFailed(String),
}

/// 解析结果：正常响应带寄存器序列，异常响应带设备侧异常码.
#[derive(Debug, PartialEq, Eq)]
pub struct ParsedResponse {
    pub slave: u8,
    pub function: u8,
    pub byte_count: u8,
    pub registers: Vec<u16>,
    pub exception: Option<u8>,
}

impl ParsedResponse {
    /// 序列化为紧凑 JSON（全数值字段，手工拼接无转义风险），返回 UTF-8 字节.
    ///
    /// 键集与 Python 参考实现（native/reference/modbus_rtu.py）逐字一致——
    /// 等价性判据要求两侧输出可逐值比对。
    pub fn to_json(&self) -> Vec<u8> {
        let mut out = String::with_capacity(24 + self.registers.len() * 7);
        out.push_str("{\"slave\":");
        out.push_str(&self.slave.to_string());
        out.push_str(",\"function\":");
        out.push_str(&self.function.to_string());
        if let Some(code) = self.exception {
            out.push_str(",\"exception\":");
            out.push_str(&code.to_string());
        } else {
            out.push_str(",\"byte_count\":");
            out.push_str(&self.byte_count.to_string());
            out.push_str(",\"registers\":[");
            for (i, reg) in self.registers.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                out.push_str(&reg.to_string());
            }
            out.push(']');
        }
        out.push('}');
        out.into_bytes()
    }
}

/// 解析一条 RTU 响应帧（输入为不含任何传输层封装的裸 ADU）.
pub fn parse_response(frame: &[u8]) -> Result<ParsedResponse, TaskError> {
    if frame.len() < 4 {
        return Err(TaskError::InvalidInput(format!(
            "RTU 帧最短 4 字节（地址+功能码+CRC16），实际 {} 字节",
            frame.len()
        )));
    }
    if frame.len() > MAX_ADU_LEN {
        return Err(TaskError::InvalidInput(format!(
            "RTU 帧最长 {} 字节，实际 {} 字节",
            MAX_ADU_LEN,
            frame.len()
        )));
    }

    // CRC 校验：线上小端（低字节在前）
    let (data, crc_wire) = frame.split_at(frame.len() - 2);
    let expected = (crc_wire[0] as u16) | ((crc_wire[1] as u16) << 8);
    let actual = crc16_modbus(data);
    if actual != expected {
        return Err(TaskError::TaskFailed(format!(
            "CRC 校验失败：计算值 0x{actual:04X}，帧携带值 0x{expected:04X}"
        )));
    }

    let slave = data[0];
    let function = data[1];
    let base = function & 0x7F;
    if base != 0x03 && base != 0x04 {
        return Err(TaskError::TaskFailed(format!(
            "不支持的功能码 0x{function:02X}（首版仅 0x03/0x04 及其异常态）"
        )));
    }

    if function & 0x80 != 0 {
        // 异常帧：地址 + 功能码(高位|0x80) + 异常码 + CRC
        if data.len() != 3 {
            return Err(TaskError::TaskFailed(format!(
                "异常帧数据区应为 3 字节（地址+功能码+异常码），实际 {}",
                data.len()
            )));
        }
        return Ok(ParsedResponse {
            slave,
            function,
            byte_count: 0,
            registers: Vec::new(),
            exception: Some(data[2]),
        });
    }

    // 正常响应：地址 + 功能码 + 字节计数 + 寄存器数据 + CRC
    if data.len() < 3 {
        return Err(TaskError::TaskFailed(
            "正常响应缺少字节计数字段".to_string(),
        ));
    }
    let byte_count = data[2] as usize;
    if byte_count % 2 != 0 {
        return Err(TaskError::TaskFailed(format!(
            "字节计数 {byte_count} 不是偶数（每寄存器 2 字节）"
        )));
    }
    if data.len() != 3 + byte_count {
        return Err(TaskError::TaskFailed(format!(
            "字节计数 {byte_count} 与帧长不一致：数据区实际 {} 字节",
            data.len() - 3
        )));
    }

    let mut registers = Vec::with_capacity(byte_count / 2);
    let mut i = 3usize;
    while i + 1 < data.len() {
        registers.push(((data[i] as u16) << 8) | data[i + 1] as u16);
        i += 2;
    }

    Ok(ParsedResponse {
        slave,
        function,
        byte_count: data[2],
        registers,
        exception: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 构造带合法 CRC（线上小端）的完整帧.
    fn frame_with_crc(data: &[u8]) -> Vec<u8> {
        let mut frame = data.to_vec();
        let crc = crc16_modbus(data);
        frame.push((crc & 0xFF) as u8);
        frame.push((crc >> 8) as u8);
        frame
    }

    #[test]
    fn crc16_matches_standard_check_value() {
        // CRC-16/MODBUS 的标准 check 值——独立于实现的锚点
        assert_eq!(crc16_modbus(b"123456789"), CRC_CHECK_VALUE);
    }

    #[test]
    fn parses_single_register_response() {
        let frame = frame_with_crc(&[0x01, 0x03, 0x02, 0x12, 0x34]);
        let parsed = parse_response(&frame).expect("合法帧应解析成功");
        assert_eq!(parsed.slave, 0x01);
        assert_eq!(parsed.function, 0x03);
        assert_eq!(parsed.byte_count, 2);
        assert_eq!(parsed.registers, vec![0x1234]);
        assert_eq!(parsed.exception, None);
        assert_eq!(parsed.to_json(), br#"{"slave":1,"function":3,"byte_count":2,"registers":[4660]}"#);
    }

    #[test]
    fn parses_multi_register_response() {
        let frame = frame_with_crc(&[0x11, 0x04, 0x04, 0x00, 0x0A, 0xFF, 0xFF]);
        let parsed = parse_response(&frame).expect("合法帧应解析成功");
        assert_eq!(parsed.registers, vec![0x000A, 0xFFFF]);
        assert_eq!(parsed.function, 0x04);
    }

    #[test]
    fn parses_exception_frame_as_successful_parse() {
        // 异常帧是"解析成功、语义为异常"——不进错误族
        let frame = frame_with_crc(&[0x01, 0x83, 0x02]);
        let parsed = parse_response(&frame).expect("异常帧应解析成功");
        assert_eq!(parsed.exception, Some(0x02));
        assert_eq!(parsed.registers, Vec::<u16>::new());
        assert_eq!(parsed.to_json(), br#"{"slave":1,"function":131,"exception":2}"#);
    }

    #[test]
    fn corrupted_crc_is_task_failed_not_invalid_input() {
        let mut frame = frame_with_crc(&[0x01, 0x03, 0x02, 0x12, 0x34]);
        let last = frame.len() - 1;
        frame[last] ^= 0xFF; // 翻转 CRC 高字节
        match parse_response(&frame) {
            Err(TaskError::TaskFailed(msg)) => assert!(msg.contains("CRC")),
            other => panic!("CRC 损坏应为 TaskFailed，实际 {other:?}"),
        }
    }

    #[test]
    fn unsupported_function_code_is_task_failed() {
        let frame = frame_with_crc(&[0x01, 0x10, 0x00]);
        match parse_response(&frame) {
            Err(TaskError::TaskFailed(msg)) => assert!(msg.contains("0x10")),
            other => panic!("未知功能码应为 TaskFailed，实际 {other:?}"),
        }
    }

    #[test]
    fn short_frame_is_invalid_input() {
        match parse_response(&[0x01, 0x03, 0x00]) {
            Err(TaskError::InvalidInput(_)) => {}
            other => panic!("3 字节帧应为 InvalidInput，实际 {other:?}"),
        }
    }

    #[test]
    fn oversized_frame_is_invalid_input() {
        let mut data = vec![0x01u8, 0x03, 0xFD]; // 253 数据字节 → 256 ADU
        data.extend(std::iter::repeat(0u8).take(252));
        let mut frame = frame_with_crc(&data);
        frame.push(0x00); // 超限 1 字节
        match parse_response(&frame) {
            Err(TaskError::InvalidInput(msg)) => assert!(msg.contains("256")),
            other => panic!("超限帧应为 InvalidInput，实际 {other:?}"),
        }
    }

    #[test]
    fn byte_count_mismatch_is_task_failed() {
        // 字节计数说 4 字节，实际只有 2 字节
        let frame = frame_with_crc(&[0x01, 0x03, 0x04, 0x12, 0x34]);
        match parse_response(&frame) {
            Err(TaskError::TaskFailed(msg)) => assert!(msg.contains("不一致")),
            other => panic!("计数不一致应为 TaskFailed，实际 {other:?}"),
        }
    }

    #[test]
    fn odd_byte_count_is_task_failed() {
        let frame = frame_with_crc(&[0x01, 0x03, 0x03, 0x12, 0x34, 0x56]);
        match parse_response(&frame) {
            Err(TaskError::TaskFailed(msg)) => assert!(msg.contains("偶数")),
            other => panic!("奇数计数应为 TaskFailed，实际 {other:?}"),
        }
    }

    #[test]
    fn max_sized_frame_parses() {
        let mut data = vec![0x01u8, 0x03, 0xFA]; // 250 数据字节 → 126 寄存器
        for i in 0..250u16 {
            data.push((i & 0xFF) as u8);
        }
        let frame = frame_with_crc(&data);
        let parsed = parse_response(&frame).expect("满尺寸帧应解析成功");
        assert_eq!(parsed.registers.len(), 125);
        assert_eq!(parsed.registers[124], 0xF8F9); // 末寄存器 = 字节 248,249
    }
}
