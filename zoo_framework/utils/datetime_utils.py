from datetime import datetime, timedelta


class DateTimeUtils:
    @classmethod
    def get_format_now(cls, format_mod: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
        return datetime.now().strftime(format_mod)

    @classmethod
    def get_format_datetime(
        cls, target_time: datetime, format_mod: str = "%Y-%m-%d %H:%M:%S.%f"
    ) -> str:
        return target_time.strftime(format_mod)

    @classmethod
    def get_sub_datetime(cls, sub_days: int) -> datetime:
        return datetime.now() + timedelta(days=sub_days)

    @classmethod
    def get_format_sub_datetime(cls, sub_days: int, format_mod: str) -> str:
        time = cls.get_sub_datetime(sub_days)
        return cls.get_format_datetime(time, format_mod)

    @classmethod
    def get_week_day(cls, date_str: str) -> str:
        week_day_dict = {
            0: "星期一",
            1: "星期二",
            2: "星期三",
            3: "星期四",
            4: "星期五",
            5: "星期六",
            6: "星期天",
        }
        date = datetime.strptime(date_str, "%Y-%m-%d")
        day = date.weekday()
        return week_day_dict[day]

    @classmethod
    def get_month_date(cls, year: int, moth: int) -> list[str]:
        now = datetime(year, moth, 1)
        delta = timedelta(days=1)
        date_list = []
        while now.month == moth:
            date_list.append(now.strftime("%Y-%m-%d"))
            now = now + delta
        return date_list

    @classmethod
    def get_next_month(cls) -> datetime:
        now = datetime.now()
        month = now.month + 1
        year = now.year
        if month > 12:
            month = 1
            year += 1
        return datetime(year=year, month=month, day=1)

    @classmethod
    def get_before_month(cls) -> datetime:
        now = datetime.now()
        month = now.month - 1
        year = now.year
        if month < 1:
            month = 12
            year -= 1
        return datetime(year=year, month=month, day=1)
