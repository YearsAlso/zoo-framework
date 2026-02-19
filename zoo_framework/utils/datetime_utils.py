"""datetime_utils - zoo_framework/utils/datetime_utils.py

日期时间工具模块，提供常用的日期时间处理功能。

功能:
- 日期时间格式化
- 时间差计算
- 时间戳转换
- 日期解析和验证

作者: XiangMeng
版本: 0.5.1-beta

from datetime import datetime, timedelta


class DateTimeUtils:
    """日期时间工具类

    提供各种日期时间相关的实用方法，包括格式化、计算和转换。
    """

    @classmethod
    def get_format_now(cls, format_mod="%Y-%m-%d %H:%M:%S.%f"):
        """获取格式化后的当前时间"""
        return datetime.now().strftime(format_mod)

    @classmethod
    def get_now_timestamp(cls):
        """获取当前时间戳（秒级）"""
        return int(datetime.now().timestamp())

    @classmethod
    def get_now_timestamp_ms(cls):
        """获取当前时间戳（毫秒级）"""
        return int(datetime.now().timestamp() * 1000)

    @classmethod
    def format_datetime(cls, dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S"):
        """格式化日期时间对象"""
        return dt.strftime(format_str)

    @classmethod
    def parse_datetime(cls, date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S"):
        """解析字符串为日期时间对象"""
        return datetime.strptime(date_str, format_str)

    @classmethod
    def get_time_delta(cls, days=0, hours=0, minutes=0, seconds=0):
        """获取时间差对象"""
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
"""
