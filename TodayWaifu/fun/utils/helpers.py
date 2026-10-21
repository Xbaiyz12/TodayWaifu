"""通用小工具：时间、文本与参数解析。"""

import datetime

_WEEKDAY_CN = ('一', '二', '三', '四', '五', '六', '日')


def today() -> datetime.date:
    return datetime.date.today()


def today_str() -> str:
    return today().isoformat()


def days_in_month(year: int, month: int) -> int:
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def parse_date(raw: str) -> datetime.date | None:
    """解析 YYYY-MM-DD。越界日期（2 月 30 日等）返回 None，由调用方提示。"""
    parts = raw.strip().split('-')
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    year, month, day = (int(part) for part in parts)
    if not 1 <= month <= 12:
        return None
    if not 1 <= day <= days_in_month(year, month):
        return None
    return datetime.date(year, month, day)


def weekday_cn(day: datetime.date) -> str:
    return _WEEKDAY_CN[day.weekday()]


def count_leading(text: str, token: str) -> int:
    """统计消息开头连续出现的 token 个数，如 "🦌🦌🦌" 对 "🦌" 得 3。"""
    if not token:
        return 0
    count = 0
    rest = text.strip()
    while rest.startswith(token):
        count += 1
        rest = rest[len(token) :].strip()
    return count


def split_args(raw: str, limit: int) -> list[str]:
    parts = raw.strip().split()
    if len(parts) <= limit:
        return parts
    # 超出部分并回最后一段，避免用户说明里的空格被吃掉
    head = parts[: limit - 1]
    tail = ' '.join(parts[limit - 1 :])
    return [*head, tail]


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def human_duration(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds} 秒'
    if seconds < 3600:
        return f'{seconds // 60} 分 {seconds % 60} 秒'
    return f'{seconds // 3600} 小时 {seconds % 3600 // 60} 分'
