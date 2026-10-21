"""打卡运势：每日幸运值卡片、幸运排行榜、非酋榜与提取背景原图。

版式与文案沿用原 NoneBot 插件（luck-plugin），数据改存 SQLModel 表。
"""

import random
import datetime
from pathlib import Path

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.ai_core.trigger_bridge import ai_return

from .texts import pick_luck_text
from .models import STATUS_PENDING, STATUS_CONFIRMED, XfLuckRecord
from .shared import reply, allowed, luck_sv, recall_bg, remember_bg, luck_library
from .xf_config import get_int, get_bool
from .point_rules import SOURCE_LUCK, grant_daily_points
from .utils.events import sender_name, sender_avatar
from .utils.avatars import fetch_avatar, fetch_avatars, qq_avatar_url
from .utils.helpers import today, today_str
from .utils.calendar_logic import sign_points
from .utils.render.luck_card import render_luck_card
from .utils.render.rank_card import RankRow, SelfInfo, render_rank_card

# 计算连续打卡时最多回溯的天数，最多这么长连签；再长也只按该上限计数
STREAK_LOOKBACK_DAYS = 400


def _luck_streak(dates: set[str], day: datetime.date) -> int:
    """连续打卡天数：从昨天往前数，今天算第 1 天。"""
    streak = 1
    cursor = day - datetime.timedelta(days=1)
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return streak


CHECKIN_DOC = """抽取并查看用户今天的每日幸运值运势卡片。
当用户说"打卡""今日运势""看看我今天的运气""抽个幸运值""测测欧气"时调用。

Args:
    text: 无需参数，留空即可
"""

RANK_DOC = """查看今日幸运值排行榜（幸运值从高到低）。
当用户问"今天谁运气最好""幸运值排行榜""欧皇榜""运势排名"时调用。

Args:
    text: 无需参数，留空即可
"""

BAD_RANK_DOC = """查看今日非酋榜（幸运值从低到高）。
当用户问"今天谁最非""非酋榜""运气最差的是谁"时调用。

Args:
    text: 无需参数，留空即可
"""

EXTRACT_DOC = """提取打卡卡片的背景原图（高清面板图）。
当用户说"提取背景""要原图""提取壁纸""发我这张图的背景"时调用。

Args:
    text: 可留空（取自己今天打卡用的那张）；也可传图片 ID 或关键词，例如 "坎特蕾拉"
"""


async def _send_rank(
    bot: Bot,
    ev: Event,
    records: list[XfLuckRecord],
    title: str,
    reverse: bool,
) -> None:
    limit = get_int('xf_luck_rank_limit')
    limit = limit if limit > 0 else 20
    ordered = sorted(records, key=lambda item: item.luck, reverse=reverse)
    selected = ordered[:limit]

    rows: list[RankRow] = []
    for index, record in enumerate(selected, start=1):
        rows.append(
            RankRow(
                rank=index,
                user_name=record.name or record.user_id,
                score=record.luck,
            )
        )

    self_rank = '未入榜'
    self_luck = '未打卡'
    self_avatar_url = sender_avatar(ev)
    for index, record in enumerate(ordered, start=1):
        if record.user_id == ev.user_id:
            self_rank = f'第 {index} 名'
            self_luck = str(record.luck)
            self_avatar_url = record.avatar or self_avatar_url
            break

    row_urls = [record.avatar or qq_avatar_url(record.user_id) for record in selected]
    images = await fetch_avatars([self_avatar_url, *row_urls])
    self_avatar = images[0]
    row_avatars = images[1:]

    bg_path = await luck_library().random()
    card = await render_rank_card(
        bg_path,
        title,
        SelfInfo(
            user_name=sender_name(ev),
            score_label=self_luck,
            rank_label=self_rank,
        ),
        rows,
        self_avatar,
        row_avatars,
    )
    remember_bg(await bot.send(MessageSegment.image(card), wait_recall=True), bg_path)

    top = '、'.join(f'{row["user_name"]}({row["score"]})' for row in rows[:5])
    ai_return(
        f'【{title}】共 {len(ordered)} 人打卡；前五名：{top or "无"}；'
        f'你的今日成绩：幸运值 {self_luck}，排名 {self_rank}'
    )


@luck_sv.on_command(
    '打卡',
    to_ai=CHECKIN_DOC,
    covers=['打卡', '今日运势', '幸运值', '每日运势', '欧气'],
    aliases=['今日老婆·打卡运势'],
)
async def checkin(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_luck_enable'):
        return

    date = today_str()
    day = today()
    name = sender_name(ev)
    avatar = sender_avatar(ev)
    record = await XfLuckRecord.get_record(ev.user_id, ev.bot_id, date)

    if record is not None and record.status == STATUS_CONFIRMED:
        return await reply(bot, f'你今天已经打过卡啦！今日幸运值：{record.luck}，明天再来哦~')

    is_retry = record is not None and record.status == STATUS_PENDING
    luck = random.randint(0, 100)
    if is_retry and record is not None:
        luck = max(record.luck, luck)

    threshold = get_int('xf_luck_retry_below')
    if not is_retry and threshold > 0 and luck < threshold:
        await XfLuckRecord.upsert(
            user_id=ev.user_id,
            bot_id=ev.bot_id,
            group_id=ev.group_id or '',
            date=date,
            luck=luck,
            name=name,
            avatar=avatar,
            bg_id='',
            bg_path='',
            status=STATUS_PENDING,
        )
        ai_return(f'用户今日首次打卡幸运值 {luck}，低于阈值 {threshold}，已让其再发一次打卡重抽。')
        return await reply(
            bot,
            '唔...今天的运势确实有点让人没法直视。\n'
            '我其实不太想把这个结果展示出来，感觉会打击到你。\n'
            '如果你真的想知道，或者想再给自己一次机会，就再发一次【打卡】吧？',
        )

    bg_path = await luck_library().random()
    bg_id = bg_path.stem if bg_path is not None else 'none'

    # 打卡与签到同属积分来源：连续打卡每天多给，同一来源每天只发一次
    recent = await XfLuckRecord.recent_confirmed_dates(
        ev.user_id,
        ev.bot_id,
        (day - datetime.timedelta(days=STREAK_LOOKBACK_DAYS)).isoformat(),
    )
    luck_streak = _luck_streak(recent, day)
    base = get_int('xf_sign_points')
    bonus = get_int('xf_sign_streak_bonus')
    gained = await grant_daily_points(
        ev.user_id,
        ev.bot_id,
        SOURCE_LUCK,
        sign_points(max(0, base), max(0, bonus), luck_streak),
    )

    await XfLuckRecord.upsert(
        user_id=ev.user_id,
        bot_id=ev.bot_id,
        group_id=ev.group_id or '',
        date=date,
        luck=luck,
        name=name,
        avatar=avatar,
        bg_id=bg_id,
        bg_path=str(bg_path) if bg_path is not None else '',
        status=STATUS_CONFIRMED,
    )

    tier_name, hint_text, quote_text, active_index = pick_luck_text(luck)
    avatar_img = await fetch_avatar(avatar)
    card = await render_luck_card(
        bg_path,
        avatar_img,
        name,
        luck,
        tier_name,
        hint_text,
        quote_text,
        active_index,
        bg_id,
    )
    sent_ids = await bot.send(MessageSegment.image(card), wait_recall=True)
    remember_bg(sent_ids, bg_path)
    if gained > 0:
        await bot.send(f'📈 本次打卡 +{gained} 积分（连续打卡 {luck_streak} 天）')
    ai_return(
        f'【今日运势打卡】{name} 的幸运值 {luck} 分，评级「{tier_name}」，'
        f'建议：{hint_text}，寄语：{quote_text}；背景面板 ID：{bg_id}；'
        f'本次 +{gained} 积分（连续打卡 {luck_streak} 天）'
    )


@luck_sv.on_command(
    ('幸运值排行榜', '幸运排行榜'),
    to_ai=RANK_DOC,
    covers=['幸运值排行榜', '今日欧皇', '运势排名'],
    aliases=['今日老婆·幸运值排行榜'],
)
async def luck_rank(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_luck_rank_enable'):
        return
    records = await XfLuckRecord.confirmed_of_day(today_str())
    if not records:
        return await reply(bot, '今天还没有人打卡哦，快来发送【打卡】抢占榜首吧！')
    await _send_rank(bot, ev, records, '今日幸运值排行榜', True)


@luck_sv.on_command(
    ('幸运值非酋榜', '非酋榜'),
    to_ai=BAD_RANK_DOC,
    covers=['非酋榜', '今日最非', '运气最差'],
    aliases=['今日老婆·幸运值非酋榜'],
)
async def luck_bad_rank(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_luck_rank_enable'):
        return
    records = await XfLuckRecord.confirmed_of_day(today_str())
    if not records:
        return await reply(bot, '今天还没有人打卡哦，快来发送【打卡】吧！')
    await _send_rank(bot, ev, records, '今日非酋排行榜（幸运值最低）', False)


@luck_sv.on_command(
    ('提取背景', '提取原图', '获取背景', '提取壁纸', '提取面板图'),
    to_ai=EXTRACT_DOC,
    covers=['提取背景原图', '打卡背景图', '面板壁纸'],
    aliases=['今日老婆·提取背景'],
)
async def extract_background(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_extract_enable'):
        return

    query = ev.text.strip()
    target: Path | None = recall_bg(ev.reply_id)
    target_id = ''

    if target is None and query:
        target = await luck_library().find(query)
        target_id = query

    if target is None:
        record = await XfLuckRecord.get_record(ev.user_id, ev.bot_id, today_str())
        if record is None or not record.bg_path:
            return await reply(
                bot,
                '你今天还没有打卡哦！请先发送【打卡】抽取专属面板壁纸，\n'
                '或回复打卡图片发送【提取背景】，也可以指定 ID（如：提取背景 1742954589383）。',
            )
        target = Path(record.bg_path)
        target_id = record.bg_id

    if target is None or not target.is_file():
        return await reply(bot, '未找到对应的面板原图，请回复打卡图片发送【提取背景】或核对图片 ID。')

    display_name = target_id or target.stem
    await bot.send(f'🎨 已为你提取面板原图【{display_name}】：')
    await bot.send(MessageSegment.image(target))
    ai_return(f'已把打卡背景原图【{display_name}】发给用户（文件：{target.name}）。')
