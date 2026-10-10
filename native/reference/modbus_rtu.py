"""Modbus RTU 响应帧解析——纯 Python 参考实现（等价性判据 + 测量基线）.

角色（native/DECISION.md 阶段 0 / tasks 3.3）：

- **等价性判据**：与 Rust 扩展（``zoo_framework_native``）在同一批样本帧上
  逐值比对，两侧输出语义一致才算任务落地；
- **1.3 四链路对照的「纯 Python」基线**：同机同运行测量用。

写法刻意与典型既有实现不同：位移式 CRC（非查表）、手工切片（非 struct）——
两个**独立**实现互为判据比「同一算法换语言」更能暴露双方共同的误读。
正确性由已知答案锚定：CRC-16/MODBUS 对 ``b"123456789"`` 的标准校验值 0x4B37。

错误分类 MUST 与 Rust 侧（native/src/modbus.rs）逐条对齐：

- InvalidInput 语义：结构上无法开始解析（长度 < 4 或 > 256）
- TaskFailed 语义：解析已开始后的受控业务失败（CRC 不符 / 功能码不支持 /
  帧结构不一致）
- 异常响应帧（0x83/0x84）是**解析成功**，异常码进输出由调用方解释
"""

# CRC-16/MODBUS 的标准 check 值（独立于本实现的锚点）
CRC_CHECK_VALUE = 0x4B37

# RTU ADU 字节上限（地址 1 + 功能码 1 + 数据 253 + CRC 2）
MAX_ADU_LEN = 256


class ReferenceInvalidInput(Exception):
    """结构性输入拒绝（对应原生契约的 NativeInvalidInput 语义）."""


class ReferenceTaskFailed(Exception):
    """受控业务失败（对应原生契约的 NativeTaskFailed 语义）."""


def crc16_modbus(data: bytes) -> int:
    """位移式 CRC-16/MODBUS（反射多项式 0xA001，初值 0xFFFF）."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build_frame(data: bytes) -> bytes:
    """给数据区追加合法 CRC（线上小端：低字节在前）构成完整 ADU."""
    crc = crc16_modbus(data)
    return data + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def parse_response(frame: bytes) -> dict:
    """解析一条 RTU 响应帧 → dict（键集与 Rust 侧 to_json 逐字一致）.

    Returns:
        正常响应 ``{"slave", "function", "byte_count", "registers"}``；
        异常响应 ``{"slave", "function", "exception"}``

    Raises:
        ReferenceInvalidInput: 帧长 < 4 或 > 256（任务无法开始）
        ReferenceTaskFailed: CRC 不符 / 功能码不支持 / 帧结构不一致
    """
    if len(frame) < 4:
        raise ReferenceInvalidInput(
            f"RTU 帧最短 4 字节（地址+功能码+CRC16），实际 {len(frame)} 字节"
        )
    if len(frame) > MAX_ADU_LEN:
        raise ReferenceInvalidInput(f"RTU 帧最长 {MAX_ADU_LEN} 字节，实际 {len(frame)} 字节")

    data = frame[:-2]
    expected = frame[-2] | (frame[-1] << 8)
    actual = crc16_modbus(data)
    if actual != expected:
        raise ReferenceTaskFailed(f"CRC 校验失败：计算值 0x{actual:04X}，帧携带值 0x{expected:04X}")

    slave = data[0]
    function = data[1]
    base = function & 0x7F
    if base not in (0x03, 0x04):
        raise ReferenceTaskFailed(f"不支持的功能码 0x{function:02X}（首版仅 0x03/0x04 及其异常态）")

    if function & 0x80:
        if len(data) != 3:
            raise ReferenceTaskFailed(
                f"异常帧数据区应为 3 字节（地址+功能码+异常码），实际 {len(data)}"
            )
        return {"slave": slave, "function": function, "exception": data[2]}

    if len(data) < 3:
        raise ReferenceTaskFailed("正常响应缺少字节计数字段")
    byte_count = data[2]
    if byte_count % 2 != 0:
        raise ReferenceTaskFailed(f"字节计数 {byte_count} 不是偶数（每寄存器 2 字节）")
    if len(data) != 3 + byte_count:
        raise ReferenceTaskFailed(
            f"字节计数 {byte_count} 与帧长不一致：数据区实际 {len(data) - 3} 字节"
        )

    registers = []
    for i in range(3, len(data), 2):
        registers.append((data[i] << 8) | data[i + 1])
    return {
        "slave": slave,
        "function": function,
        "byte_count": byte_count,
        "registers": registers,
    }
