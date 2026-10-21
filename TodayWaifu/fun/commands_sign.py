"""每日签到与积分：签到横图、连签统计与积分入账。"""

import datetime

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.ai_core.trigger_bridge import ai_return

from .texts import pick_blessing
from .models import XfSignRecord, XfPointRecord
from .shared import reply, allowed, sign_sv, sign_library
from .xf_config import get_int, get_bool
from .point_rules import SOURCE_SIGN, grant_daily_points
from .utils.events import sender_name, sender_avatar
from .utils.avatars import fetch_avatar
from .utils.helpers import today, weekday_cn
from .utils.calendar_logic import sign_title, sign_points, longest_streak
from .utils.render.sign_card import SignCardData, render_sign_card

SIGN_DOC = """完成今天的每日签到，回一张签到横图并发放积分。
当用户说"签到""打卡签到""签个到""今天签到了吗"时调用。

Args:
    text: 无需参数，留空即可
"""

STATS_DOC = """查看用户自己的签到统计与积分余额。
当用户说"我的签到""签到统计""我有多少积分"时调用。

Args:
    text: 无需参数，留空即可
"""


def _streak_after(last_date: str | None, last_streak: int, date: datetime.date) -> int:
    yesterday = (date - datetime.timedelta(days=1)).isoformat()
    if last_date == yesterday:
        return last_streak + 1
    return 1


@sign_sv.on_fullmatch(
    ('签到', '签个到'),
    to_ai=SIGN_DOC,
    covers=['签到', '每日签到', '签个到'],
    aliases=['今日老婆·签到'],
)
async def do_sign(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_sign_enable'):
        return

    day = today()
    date = day.isoformat()
    history = await XfSignRecord.history(ev.user_id, ev.bot_id)
    existing = await XfSignRecord.get_day(ev.user_id, ev.bot_id, date)
    if existing is not None:
        return await reply(bot, f'你今天已经签到过啦！连续 {existing.streak} 天，累计 {len(history)} 天，明天再来～')

    last = await XfSignRecord.last_before(ev.user_id, ev.bot_id, date)
    streak = _streak_after(last.date if last is not None else None, last.streak if last is not None else 0, day)

    base = get_int('xf_sign_points')
    bonus = get_int('xf_sign_streak_bonus')
    # 应发分数含连签加成；同一来源每天只发一次（防免签道具重置后重复领取）
    computed = sign_points(max(0, base), max(0, bonus), streak)
    gained = await grant_daily_points(ev.user_id, ev.bot_id, SOURCE_SIGN, computed)

    await XfSignRecord.add(
        user_id=ev.user_id,
        bot_id=ev.bot_id,
        group_id=ev.group_id or '',
        date=date,
        streak=streak,
        points=gained,
        name=sender_name(ev),
    )
    points = await XfPointRecord.get_record(ev.user_id, ev.bot_id)
    balance = points.points if points is not None else 0

    total_days = len(history) + 1
    dates = {datetime.date.fromisoformat(record.date) for record in history}
    dates.add(day)
    blessing = pick_blessing()

    bg_path = await sign_library().random()
    avatar = await fetch_avatar(sender_avatar(ev))
    card = await render_sign_card(
        bg_path,
        avatar,
        SignCardData(
            name=sender_name(ev),
            date_label=f'{date} 星期{weekday_cn(day)}',
            streak=streak,
            total_days=total_days,
            gained=gained,
            balance=balance,
            blessing=blessing,
            title=sign_title(streak),
        ),
    )
    await bot.send(MessageSegment.image(card))
    ai_return(
        f'【签到成功】{sender_name(ev)}：连续 {streak} 天，累计 {total_days} 天，'
        f'本次 +{gained} 积分，余额 {balance}，称号「{sign_title(streak)}」，最长连签 {longest_streak(dates)} 天'
    )


@sign_sv.on_command(
    ('我的签到', '签到统计', '签到信息'),
    to_ai=STATS_DOC,
    covers=['签到统计', '我的积分', '签到情况'],
    aliases=['今日老婆·签到统计'],
)
async def sign_stats(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_sign_enable'):
        return

    history = await XfSignRecord.history(ev.user_id, ev.bot_id)
    points = await XfPointRecord.get_record(ev.user_id, ev.bot_id)
    balance = points.points if points is not None else 0

    if not history:
        return await reply(bot, f'你还没有签到过哦，发【签到】开始第一天吧！（当前积分：{balance}）')

    dates = {datetime.date.fromisoformat(record.date) for record in history}
    day = today()
    existing = await XfSignRecord.get_day(ev.user_id, ev.bot_id, day.isoformat())
    current_streak = existing.streak if existing is not None else 0
    lines = [
        f'📅 {sender_name(ev)} 的签到统计',
        f'累计签到：{len(history)} 天',
        f'当前连签：{current_streak} 天',
        f'最长连签：{longest_streak(dates)} 天',
        f'首次签到：{min(record.date for record in history)}',
        f'最近签到：{max(record.date for record in history)}',
        f'称号：{sign_title(max(current_streak, longest_streak(dates)))}',
        f'积分余额：{balance}',
        '今天还没签到哦～' if existing is None else '今天已签到 ✓',
    ]
    await bot.send('\n'.join(lines))
    ai_return(
        f'【签到统计】{sender_name(ev)}：累计 {len(history)} 天，当前连签 {current_streak} 天，'
        f'最长连签 {longest_streak(dates)} 天，积分余额 {balance}'
    )
