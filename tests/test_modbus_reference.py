"""Modbus RTU 纯 Python 参考实现的已知答案与分类测试.

参考实现是 Rust 扩展的等价性判据——它自己的正确性靠**独立已知答案**锚定
（CRC-16/MODBUS 标准 check 值），不靠与 Rust 互证。
"""

import importlib.util
from pathlib import Path

import pytest

# 参考实现不在任何包内（native/ 是 crate 目录，不入主包 wheel）——按文件路径加载
_REFERENCE_PATH = Path(__file__).resolve().parents[1] / "native" / "reference" / "modbus_rtu.py"
_spec = importlib.util.spec_from_file_location("modbus_reference", _REFERENCE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CRC_CHECK_VALUE = _mod.CRC_CHECK_VALUE
ReferenceInvalidInput = _mod.ReferenceInvalidInput
ReferenceTaskFailed = _mod.ReferenceTaskFailed
build_frame = _mod.build_frame
crc16_modbus = _mod.crc16_modbus
parse_response = _mod.parse_response


def test_crc16_matches_standard_check_value():
    """独立锚点：CRC-16/MODBUS("123456789") == 0x4B37."""
    assert crc16_modbus(b"123456789") == CRC_CHECK_VALUE


def test_frame_crc_is_little_endian_on_wire():
    """构造帧的 CRC 低字节在前（线上小端）——翻转两字节必须触发 CRC 失败."""
    frame = build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34]))
    swapped = frame[:-2] + bytes([frame[-1], frame[-2]])
    with pytest.raises(ReferenceTaskFailed, match="CRC"):
        parse_response(swapped)


def test_parse_single_register_response():
    parsed = parse_response(build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34])))
    assert parsed == {
        "slave": 1,
        "function": 3,
        "byte_count": 2,
        "registers": [0x1234],
    }


def test_parse_exception_frame_is_successful_parse():
    """异常帧不进错误族：解析成功，异常码进输出."""
    parsed = parse_response(build_frame(bytes([0x01, 0x83, 0x02])))
    assert parsed == {"slave": 1, "function": 0x83, "exception": 2}


class TestErrorClassification:
    def test_short_frame_is_invalid_input(self):
        with pytest.raises(ReferenceInvalidInput):
            parse_response(b"\x01\x03\x00")

    def test_oversized_frame_is_invalid_input(self):
        with pytest.raises(ReferenceInvalidInput):
            parse_response(bytes(257))

    def test_corrupted_crc_is_task_failed(self):
        frame = bytearray(build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34])))
        frame[-1] ^= 0xFF
        with pytest.raises(ReferenceTaskFailed, match="CRC"):
            parse_response(bytes(frame))

    def test_unsupported_function_code_is_task_failed(self):
        with pytest.raises(ReferenceTaskFailed, match="0x10"):
            parse_response(build_frame(bytes([0x01, 0x10, 0x00])))

    def test_byte_count_mismatch_is_task_failed(self):
        # 字节计数说 4，实际数据区只有 2 字节
        with pytest.raises(ReferenceTaskFailed, match="不一致"):
            parse_response(build_frame(bytes([0x01, 0x03, 0x04, 0x12, 0x34])))

    def test_odd_byte_count_is_task_failed(self):
        with pytest.raises(ReferenceTaskFailed, match="偶数"):
            parse_response(build_frame(bytes([0x01, 0x03, 0x03, 0x12, 0x34, 0x56])))
