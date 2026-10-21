"""鹿 / 扣 日历与签到的纯逻辑层：周期解析、月历网格、连续天数、称号与聚合。

这一层不碰数据库与图片，全部是纯函数，方便直接单测。
"""

import calendar
import datetime
from dataclasses import dataclass

from .helpers import days_in_month

CALENDAR_TITLES: tuple[tuple[int, str], ...] = (
    (500, '之王'),
    (200, '大师'),
    (50, '老手'),
    (10, '熟练工'),
    (1, '新手'),
)

SIGN_TITLES: tuple[tuple[int, str], ...] = (
    (365, '签到之神'),
    (100, '百日不辍'),
    (30, '月度全勤'),
    (7, '一周不断'),
    (3, '渐入佳境'),
    (1, '刚刚起步'),
)


@dataclass(frozen=True)
class Period:
    """统计周期：某个月或某一年。year 周期时 month 为 0。"""

    kind: str
    year: int
    month: int = 0

    @property
    def is_year(self) -> bool:
        return self.kind == 'year'

    @property
    def label(self) -> str:
        if self.is_year:
            return f'{self.year} 年'
        return f'{self.year} 年 {self.month} 月'

    def start_date(self) -> str:
        if self.is_year:
            return datetime.date(self.year, 1, 1).isoformat()
        return datetime.date(self.year, self.month, 1).isoformat()

    def end_date(self) -> str:
        if self.is_year:
            return datetime.date(self.year, 12, 31).isoformat()
        return datetime.date(self.year, self.month, days_in_month(self.year, self.month)).isoformat()


@dataclass(frozen=True)
class ShopItem:
    name: str
    cost: int
    desc: str


def parse_period(raw: str, base: datetime.date) -> Period | None:
    """解析统计周期：留空=本月，`11`=11 月，`2026`=全年，`2026-11`=指定月。"""
    text = raw.strip().replace('/', '-')
    if not text:
        return Period('month', base.year, base.month)
    if text.isdigit():
        number = int(text)
        if number >= 1000:
            return Period('year', number, 0)
        if 1 <= number <= 12:
            return Period('month', base.year, number)
        return None
    parts = text.split('-')
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        year, month = int(parts[0]), int(parts[1])
        if 1000 <= year <= 9999 and 1 <= month <= 12:
            return Period('month', year, month)
    return None


def month_weeks(year: int, month: int) -> list[list[int]]:
    """月历网格（周一为一周第一天），未使用的位置为 0。"""
    return calendar.monthcalendar(year, month)


def aggregate(days: list[tuple[str, int]]) -> dict[str, int]:
    """把 (日期, 次数) 列表聚合成 {日期: 总次数}。"""
    result: dict[str, int] = {}
    for day, count in days:
        result[day] = result[day] + count if day in result else count
    return result


def streak_from_days(day_counts: dict[str, int], today: datetime.date) -> int:
    """从今天往回数连续有记录的天数；今天没记录则从昨天起算。"""
    cursor = today if today.isoformat() in day_counts else today - datetime.timedelta(days=1)
    streak = 0
    while cursor.isoformat() in day_counts:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return streak


def longest_streak(dates: set[datetime.date]) -> int:
    if not dates:
        return 0
    ordered = sorted(dates)
    best = 1
    current = 1
    for index in range(1, len(ordered)):
        if (ordered[index] - ordered[index - 1]).days == 1:
            current += 1
        else:
            current = 1
        best = max(best, current)
    return best


def best_day(day_counts: dict[str, int]) -> tuple[str, int] | None:
    if not day_counts:
        return None
    day = max(day_counts, key=lambda key: day_counts[key])
    return (day, day_counts[day])


def top_users(rows: list[tuple[str, str, int]], limit: int) -> list[tuple[str, str, int]]:
    """按用户聚合 (user_id, name, 次数) 并降序取前 limit 名。"""
    totals: dict[str, int] = {}
    names: dict[str, str] = {}
    order: list[str] = []
    for user_id, name, count in rows:
        if user_id not in totals:
            totals[user_id] = 0
            order.append(user_id)
        totals[user_id] += count
        names[user_id] = name
    ranked = [(user_id, names[user_id], totals[user_id]) for user_id in order]
    ranked.sort(key=lambda item: (-item[2], item[0]))
    return ranked[:limit]


def calendar_title(name: str, total: int) -> str:
    for threshold, title in CALENDAR_TITLES:
        if total >= threshold:
            return f'{name}{title}'
    return f'路过的{name}'


def sign_title(streak: int) -> str:
    for threshold, title in SIGN_TITLES:
        if streak >= threshold:
            return title
    return '尚未开始'


def sign_points(base: int, bonus: int, streak: int) -> int:
    """基础分 + 连签加成；加成封顶为基础分的 3 倍，防止长连签积分爆炸。"""
    extra = min(bonus * max(0, streak - 1), base * 3)
    return base + extra


def parse_shop_item(raw: str) -> ShopItem | None:
    """解析 `名称|价格|说明`（说明可省略）。"""
    parts = [part.strip() for part in raw.split('|')]
    if len(parts) < 2:
        return None
    name, cost_text = parts[0], parts[1]
    if not name or not cost_text.isdigit():
        return None
    cost = int(cost_text)
    if cost <= 0:
        return None
    desc = parts[2] if len(parts) > 2 else ''
    return ShopItem(name=name, cost=cost, desc=desc)


def month_marks(day_counts: dict[str, int], year: int, month: int) -> dict[int, int]:
    """把 {YYYY-MM-DD: 次数} 收成 {日: 次数}，只保留目标月份。"""
    prefix = f'{year:04d}-{month:02d}-'
    marks: dict[int, int] = {}
    for day, count in day_counts.items():
        if not day.startswith(prefix):
            continue
        day_text = day[len(prefix) :]
        if day_text.isdigit():
            marks[int(day_text)] = count
    return marks
