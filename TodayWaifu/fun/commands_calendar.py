"""鹿 / 扣 人品日历：发 emoji 即打卡，另有人品日历图、排行、生涯、战报与更正。

鹿（🦌 / 鹿打卡）与扣（扣 / 🤏）两套计数完全平行、互不影响。
"""

import datetime
from typing import Literal, Callable, Awaitable

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.ai_core.trigger_bridge import ai_return

from .models import XfCalendarRecord
from .shared import (
    KOU_THEME,
    DEER_THEME,
    Theme,
    reply,
    has_pm,
    allowed,
    theme_cap,
    theme_icon,
    theme_line,
    theme_name,
    calendar_sv,
    theme_enabled,
)
from .xf_config import get_int, get_bool
from .utils.events import sender_name, sender_avatar
from .utils.avatars import fetch_avatars, qq_avatar_url
from .utils.helpers import today, parse_date, split_args, weekday_cn, count_leading, days_in_month
from .utils.calendar_logic import (
    best_day,
    aggregate,
    top_users,
    month_marks,
    parse_period,
    calendar_title,
    longest_streak,
    streak_from_days,
)
from .utils.render.rank_card import RankRow, SelfInfo, render_rank_card
from .utils.render.calendar_card import CalendarSummary, render_calendar_card

CalendarAction = Literal['checkin', 'month', 'year', 'life', 'report', 'rank', 'group', 'add', 'sub', 'clear']

ActionFunc = Callable[[Bot, Event, Theme, str], Awaitable[None]]

SUB_ACTIONS: tuple[CalendarAction, ...] = (
    'month',
    'year',
    'life',
    'report',
    'rank',
    'group',
    'add',
    'sub',
    'clear',
)

SUFFIX: dict[CalendarAction, str] = {
    'checkin': '打卡',
    'month': '日历',
    'year': '年历',
    'life': '生涯',
    'report': '报告',
    'rank': '排行',
    'group': '群报',
    'add': '补签',
    'sub': '撤销',
    'clear': '清空',
}

COVER_HINTS: dict[CalendarAction, tuple[str, ...]] = {
    'checkin': ('打卡',),
    'month': ('日历', '月历'),
    'year': ('年历', '年度统计'),
    'life': ('生涯', '统计'),
    'report': ('报告', '分析'),
    'rank': ('排行', '排行榜', '榜'),
    'group': ('群报', '战报'),
    'add': ('补签',),
    'sub': ('撤销',),
    'clear': ('清空',),
}


def _as_records(records: list[XfCalendarRecord]) -> list[tuple[str, str, int]]:
    return [(record.user_id, record.name, record.count) for record in records]


def _day_counts(records: list[XfCalendarRecord]) -> dict[str, int]:
    return aggregate([(record.date, record.count) for record in records])


async def _send_month_card(bot: Bot, theme: Theme, ev: Event, year: int, month: int, line: str) -> None:
    name = theme_name(theme)
    first_day = datetime.date(year, month, 1)
    last_day = datetime.date(year, month, days_in_month(year, month))
    month_records = await XfCalendarRecord.range_records(
        theme.key,
        ev.bot_id,
        first_day.isoformat(),
        last_day.isoformat(),
        user_id=ev.user_id,
    )
    all_records = await XfCalendarRecord.all_records(theme.key, ev.user_id, ev.bot_id)
    counts = _day_counts(month_records)
    life_total = sum(record.count for record in all_records)
    life_days = len({record.date for record in all_records})
    streak = streak_from_days(_day_counts(all_records), today())

    summary = CalendarSummary(
        name=name,
        year=year,
        month=month,
        days=len(counts),
        total=sum(counts.values()),
        streak=streak,
        life_total=life_total,
        life_days=life_days,
        title=calendar_title(name, life_total),
        line=line,
    )
    card = await render_calendar_card(theme_icon(theme), summary, month_marks(counts, year, month))
    await bot.send(MessageSegment.image(card))
    ai_return(
        f'【{name}打卡日历】{year} 年 {month} 月：打卡 {summary["days"]} 天 / {summary["total"]} 次；'
        f'当前连签 {streak} 天；生涯累计 {life_total} 次 / {life_days} 天；称号「{summary["title"]}」'
    )


def _count_tokens(theme: Theme, raw_text: str) -> int:
    """emoji 触发时 ev.command 可能为空（正则），这里按主题自己数一遍。"""
    amount = 0
    for token in (theme.word, *theme.emoji, f'{theme.word}打卡'):
        amount = max(amount, count_leading(raw_text, token))
    return amount or 1


async def _do_checkin(bot: Bot, ev: Event, theme: Theme, _args: str) -> None:
    name = theme_name(theme)
    amount = _count_tokens(theme, ev.raw_text)
    counted, total = await XfCalendarRecord.change_count(
        theme=theme.key,
        user_id=ev.user_id,
        bot_id=ev.bot_id,
        group_id=ev.group_id or '',
        date=today().isoformat(),
        name=sender_name(ev),
        delta=amount,
        cap=theme_cap(theme),
    )
    if counted == 0:
        return await reply(bot, f'今天已经记满 {total} 次{name}啦，明天再来吧～')
    await _send_month_card(bot, theme, ev, today().year, today().month, f'{theme_line(theme)}（今日共 {total} 次）')


async def _do_month(bot: Bot, ev: Event, theme: Theme, args: str) -> None:
    period = parse_period(args, today())
    if period is None or period.is_year:
        return await reply(bot, f'月份没看懂哦，可以发【{theme.word}日历 11】看看 11 月。')
    await _send_month_card(bot, theme, ev, period.year, period.month, theme_line(theme))


async def _do_year(bot: Bot, ev: Event, theme: Theme, args: str) -> None:
    name = theme_name(theme)
    text = args.strip()
    year = today().year
    if text:
        if not text.isdigit() or not 1000 <= int(text) <= 9999:
            return await reply(bot, f'年份没看懂哦，可以发【{theme.word}年历 2026】。')
        year = int(text)

    records = await XfCalendarRecord.range_records(
        theme.key,
        ev.bot_id,
        datetime.date(year, 1, 1).isoformat(),
        datetime.date(year, 12, 31).isoformat(),
        user_id=ev.user_id,
    )
    if not records:
        return await reply(bot, f'{year} 年还没有{name}记录哦，发【{theme.word}】就可以打卡啦！')

    counts = _day_counts(records)
    total = sum(counts.values())
    lines = [f'📅 {year} 年{name}历（{calendar_title(name, total)}）']
    for month in range(1, 13):
        month_counts = {day: count for day, count in counts.items() if day.startswith(f'{year}-{month:02d}-')}
        days = len(month_counts)
        times = sum(month_counts.values())
        bar = '█' * min(10, days)
        lines.append(f'{month:>2} 月 {bar or "·"} {days} 天 / {times} 次')
    lines.append(f'合计：{len(counts)} 天 / {total} 次')
    await bot.send('\n'.join(lines))
    ai_return(f'【{name}年历】{year} 年累计 {len(counts)} 天 / {total} 次。')


async def _do_life(bot: Bot, ev: Event, theme: Theme, _args: str) -> None:
    name = theme_name(theme)
    records = await XfCalendarRecord.all_records(theme.key, ev.user_id, ev.bot_id)
    if not records:
        return await reply(bot, f'你还没有{name}记录哦，发【{theme.word}】开始第一次吧！')

    counts = _day_counts(records)
    total = sum(counts.values())
    days = sorted(counts)
    dates = {datetime.date.fromisoformat(day) for day in days}
    peak = best_day(counts)
    lines = [
        f'📊 {sender_name(ev)} 的{name}生涯',
        f'累计次数：{total} 次',
        f'打卡天数：{len(days)} 天',
        f'最长连签：{longest_streak(dates)} 天',
        f'当前连签：{streak_from_days(counts, today())} 天',
        f'首次记录：{days[0]}',
        f'最近记录：{days[-1]}',
        f'最猛一天：{peak[0]}（{peak[1]} 次）' if peak is not None else '最猛一天：暂无',
        f'称号：{calendar_title(name, total)}',
    ]
    await bot.send('\n'.join(lines))
    ai_return(
        f'【{name}生涯】{sender_name(ev)} 累计 {total} 次 / {len(days)} 天，称号「{calendar_title(name, total)}」'
    )


async def _do_report(bot: Bot, ev: Event, theme: Theme, args: str) -> None:
    name = theme_name(theme)
    period = parse_period(args, today())
    if period is None:
        return await reply(bot, f'周期没看懂哦，可以发【{theme.word}报告 11】或【{theme.word}报告 2026】。')

    records = await XfCalendarRecord.range_records(
        theme.key,
        ev.bot_id,
        period.start_date(),
        period.end_date(),
        user_id=ev.user_id,
    )
    counts = _day_counts(records)
    total = sum(counts.values())
    if total == 0:
        return await reply(bot, f'{period.label}你还没有{name}记录哦～')

    peak = best_day(counts)
    lines = [
        f'📈 {sender_name(ev)} 的{name}报告 · {period.label}',
        f'打卡天数：{len(counts)} 天',
        f'总次数：{total} 次',
        f'日均次数：{total / len(counts):.1f} 次',
        f'最猛一天：{peak[0]}（{peak[1]} 次）' if peak is not None else '最猛一天：暂无',
        f'区间：{min(counts)} ~ {max(counts)}',
        f'评价：{calendar_title(name, total)}',
    ]
    await bot.send('\n'.join(lines))
    ai_return(f'【{name}报告】{period.label}：{len(counts)} 天 / {total} 次。')


async def _do_rank(bot: Bot, ev: Event, theme: Theme, args: str) -> None:
    if ev.group_id is None:
        return await reply(bot, '排行榜要在群里用哦～')

    name = theme_name(theme)
    period = parse_period(args, today())
    if period is None:
        return await reply(bot, f'周期没看懂哦，可以发【{theme.word}排行 11】或【{theme.word}排行 2026】。')

    records = await XfCalendarRecord.range_records(
        theme.key,
        ev.bot_id,
        period.start_date(),
        period.end_date(),
        group_id=ev.group_id,
    )
    if not records:
        return await reply(bot, f'{period.label}本群还没有{name}记录哦！')

    ranked = top_users(_as_records(records), 15)
    rows: list[RankRow] = []
    for index, (user_id, member_name, count) in enumerate(ranked, start=1):
        rows.append(RankRow(rank=index, user_name=member_name or user_id, score=count))

    self_rank_label = '未入榜'
    self_score = '0'
    for index, (user_id, _, count) in enumerate(ranked, start=1):
        if user_id == ev.user_id:
            self_rank_label = f'第 {index} 名'
            self_score = str(count)
            break

    urls = [qq_avatar_url(user_id) for user_id, _, _ in ranked]
    images = await fetch_avatars([sender_avatar(ev), *urls])
    card = await render_rank_card(
        None,
        f'{period.label}{name}打卡排行',
        SelfInfo(user_name=sender_name(ev), score_label=self_score, rank_label=self_rank_label),
        rows,
        images[0],
        images[1:],
    )
    await bot.send(MessageSegment.image(card))
    top_text = '、'.join(f'{member_name or user_id}({count})' for user_id, member_name, count in ranked[:5])
    ai_return(f'【{name}排行】{period.label}前五：{top_text}；你的成绩：{self_score} 次，{self_rank_label}')


async def _do_group_report(bot: Bot, ev: Event, theme: Theme, _args: str) -> None:
    if ev.group_id is None:
        return await reply(bot, '群战报要在群里用哦～')

    name = theme_name(theme)
    day = today()
    first_record = await XfCalendarRecord.first_of_day(theme.key, ev.bot_id, day.isoformat(), ev.group_id)
    today_records = await XfCalendarRecord.range_records(
        theme.key, ev.bot_id, day.isoformat(), day.isoformat(), group_id=ev.group_id
    )
    month_records = await XfCalendarRecord.range_records(
        theme.key,
        ev.bot_id,
        datetime.date(day.year, day.month, 1).isoformat(),
        day.isoformat(),
        group_id=ev.group_id,
    )
    last_monday = day - datetime.timedelta(days=day.weekday() + 7)
    week_records = await XfCalendarRecord.range_records(
        theme.key,
        ev.bot_id,
        last_monday.isoformat(),
        (last_monday + datetime.timedelta(days=6)).isoformat(),
        group_id=ev.group_id,
    )

    today_total = sum(record.count for record in today_records)
    month_total = sum(record.count for record in month_records)
    month_users = len({record.user_id for record in month_records})
    month_top = top_users(_as_records(month_records), 3)
    week_top = top_users(_as_records(week_records), 1)

    lines = [
        f'📋 本群{name}战报 · {day.isoformat()}（周{weekday_cn(day)}）',
        f'今日首{name}：{first_record.name or first_record.user_id}'
        if first_record is not None
        else f'今日首{name}：还空着',
        f'今日概况：{len(today_records)} 人 / {today_total} 次',
        f'上周{name}王：{week_top[0][1] or week_top[0][0]}（{week_top[0][2]} 次）' if week_top else f'上周{name}王：无',
        f'本月概况：{month_users} 人 / {month_total} 次',
    ]
    if month_top:
        ranking = '、'.join(f'{member_name or user_id}({count})' for user_id, member_name, count in month_top)
        lines.append(f'本月前三：{ranking}')
    await bot.send('\n'.join(lines))
    ai_return(
        f'【{name}群报】今日 {len(today_records)} 人 / {today_total} 次；本月 {month_users} 人 / {month_total} 次。'
    )


def _resolve_fix_day(args: str) -> tuple[datetime.date | None, int]:
    """解析「日期 [次数]」：日期可以是当月几号，也可以是 YYYY-MM-DD。"""
    parts = split_args(args, 2)
    if not parts:
        return (None, 1)

    amount = 1
    if len(parts) >= 2 and parts[1].isdigit():
        amount = int(parts[1])
    if amount <= 0:
        return (None, amount)

    text = parts[0]
    if text.isdigit():
        day_number = int(text)
        base = today()
        if not 1 <= day_number <= days_in_month(base.year, base.month):
            return (None, amount)
        return (base.replace(day=day_number), amount)
    return (parse_date(text), amount)


async def _do_fix(bot: Bot, ev: Event, theme: Theme, args: str) -> None:
    if not has_pm(ev, get_int('xf_calendar_fix_pm')):
        return await reply(bot, '你的权限还不够更正记录哦～')

    name = theme_name(theme)
    day, amount = _resolve_fix_day(args)
    if day is None or amount <= 0:
        return await reply(bot, f'用法：{theme.word}补签 日期 [次数]，例如 {theme.word}补签 18 2')

    counted, total = await XfCalendarRecord.change_count(
        theme=theme.key,
        user_id=ev.user_id,
        bot_id=ev.bot_id,
        group_id=ev.group_id or '',
        date=day.isoformat(),
        name=sender_name(ev),
        delta=amount,
        cap=0,
    )
    await bot.send(f'已为 {day.isoformat()} 补记 {counted} 次{name}，当天共 {total} 次。')


async def _do_undo(bot: Bot, ev: Event, theme: Theme, args: str) -> None:
    if not has_pm(ev, get_int('xf_calendar_fix_pm')):
        return await reply(bot, '你的权限还不够更正记录哦～')

    name = theme_name(theme)
    day, amount = _resolve_fix_day(args)
    if day is None or amount <= 0:
        return await reply(bot, f'用法：{theme.word}撤销 日期 [次数]，例如 {theme.word}撤销 18 1')

    counted, total = await XfCalendarRecord.change_count(
        theme=theme.key,
        user_id=ev.user_id,
        bot_id=ev.bot_id,
        group_id=ev.group_id or '',
        date=day.isoformat(),
        name=sender_name(ev),
        delta=-amount,
        cap=0,
    )
    await bot.send(f'已从 {day.isoformat()} 撤销 {-counted} 次{name}，当天剩余 {total} 次。')


async def _do_clear(bot: Bot, ev: Event, theme: Theme, _args: str) -> None:
    if not has_pm(ev, get_int('xf_calendar_fix_pm')):
        return await reply(bot, '你的权限还不够清空记录哦～')
    name = theme_name(theme)
    removed = await XfCalendarRecord.clear_user(theme.key, ev.user_id, ev.bot_id)
    if removed == 0:
        return await reply(bot, f'你还没有{name}记录可以清空哦。')
    await bot.send(f'已清空你的{name}记录（{removed} 天），数据不可恢复。')


DISPATCH: dict[CalendarAction, ActionFunc] = {
    'checkin': _do_checkin,
    'month': _do_month,
    'year': _do_year,
    'life': _do_life,
    'report': _do_report,
    'rank': _do_rank,
    'group': _do_group_report,
    'add': _do_fix,
    'sub': _do_undo,
    'clear': _do_clear,
}


def _action_enabled(action: CalendarAction, theme: Theme) -> bool:
    """主题开关 + 子功能开关：排行/群报、统计、更正各自一个控制台开关。"""
    if not theme_enabled(theme):
        return False
    if action in ('year', 'life', 'report'):
        return get_bool('xf_calendar_stats_enable')
    if action in ('rank', 'group'):
        return get_bool('xf_calendar_rank_enable')
    if action in ('add', 'sub', 'clear'):
        return get_bool('xf_calendar_fix_enable')
    return True


def _make_handler(theme: Theme, action: CalendarAction) -> Callable[[Bot, Event], Awaitable[None]]:
    async def handler(bot: Bot, ev: Event) -> None:
        if not await allowed(ev) or not _action_enabled(action, theme):
            return
        await DISPATCH[action](bot, ev, theme, ev.text)

    handler.__name__ = f'xf_calendar_{theme.key}_{action}'
    handler.__qualname__ = handler.__name__
    return handler


def _doc(action: CalendarAction, theme: Theme) -> str:
    word = theme.word
    name = theme_name(theme)
    if action == 'checkin':
        return f"""给用户记一次{name}打卡（人品日历），并回一张本月{name}日历图。
当用户说"{word}""{word}打卡""今天{word}一下"时调用。

Args:
    text: 无需参数，留空即可
"""
    if action == 'month':
        return f"""查看用户指定月份的{name}打卡日历图。
当用户说"看{word}日历""{word}月历""上个月{word}了多少"时调用。

Args:
    text: 月份或年月，可留空（本月）。例如 "11"（今年 11 月）、"2026-11"
"""
    if action == 'year':
        return f"""查看用户某年的{name}打卡年度统计。
当用户说"{word}年历""今年{word}了多少次"时调用。

Args:
    text: 年份，可留空（今年）。例如 "2026"
"""
    if action == 'life':
        return f"""查看用户的{name}生涯统计与称号。
当用户说"{word}生涯""我{word}了多少次""我的{word}称号"时调用。

Args:
    text: 无需参数，留空即可
"""
    if action == 'report':
        return f"""查看用户某个周期的{name}打卡分析报告。
当用户说"{word}报告""{word}分析""这个月{word}得怎么样"时调用。

Args:
    text: 周期，可留空（本月）。例如 "11"、"2026"
"""
    if action == 'rank':
        return f"""查看本群{name}打卡排行榜。
当用户说"{word}排行""{word}榜""谁{word}得最多"时调用。

Args:
    text: 周期，可留空（本月）。例如 "11"、"2026"
"""
    if action == 'group':
        return f"""生成本群{name}打卡战报（今日首{word}、今日概况、上周{word}王、本月前三）。
当用户说"{word}群报""本群{word}战报"时调用。

Args:
    text: 无需参数，留空即可
"""
    if action == 'add':
        return f"""为某个日期补记{name}打卡次数（仅限有权限的用户）。
当用户说"{word}补签""帮我补一下昨天的{word}"时调用。

Args:
    text: 日期 [次数]，日期为当月几号或 YYYY-MM-DD。例如 "18"、"18 2"、"2026-11-18 1"
"""
    if action == 'sub':
        return f"""为某个日期撤销{name}打卡次数（仅限有权限的用户）。
当用户说"{word}撤销""把我多记的{word}去掉"时调用。

Args:
    text: 日期 [次数]，日期为当月几号或 YYYY-MM-DD。例如 "18"、"18 1"
"""
    return f"""清空用户的全部{name}打卡记录（仅限有权限的用户，不可恢复）。
当用户明确说"清空我的{word}记录""{word}清空"时调用。

Args:
    text: 无需参数，留空即可
"""


def _register_theme(theme: Theme) -> None:
    word = theme.word
    # 显示名与 AI 描述在导入期定型：改控制台里的显示名要重载插件才刷新
    name = theme_name(theme)
    for action in SUB_ACTIONS:
        covers = [f'{name}{hint}' for hint in COVER_HINTS[action]]
        calendar_sv.on_command(
            f'{word}{SUFFIX[action]}',
            to_ai=_doc(action, theme),
            covers=covers,
            aliases=[f'今日老婆·{name}{SUFFIX[action]}'],
        )(_make_handler(theme, action))


def _register_checkin() -> None:
    calendar_sv.on_command(
        ('🦌', '鹿打卡'),
        to_ai=_doc('checkin', DEER_THEME),
        covers=['鹿打卡', '鹿', '今天鹿一下'],
        aliases=[f'今日老婆·{theme_name(DEER_THEME)}打卡'],
    )(_make_handler(DEER_THEME, 'checkin'))

    # 扣 与「扣日历」等子命令前缀重叠，用锚定正则只吃纯打卡消息，避免同一条消息触发两次
    calendar_sv.on_regex(
        r'^(?:扣+|🤏+|扣打卡)$',
        to_ai=_doc('checkin', KOU_THEME),
        covers=['扣打卡', '扣', '今天扣一下'],
        aliases=[f'今日老婆·{theme_name(KOU_THEME)}打卡'],
    )(_make_handler(KOU_THEME, 'checkin'))


_register_checkin()
_register_theme(DEER_THEME)
_register_theme(KOU_THEME)
