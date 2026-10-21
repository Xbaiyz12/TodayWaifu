"""群聊小游戏：掷骰子、猜数字、石头剪刀布与俄罗斯轮盘。"""

import re
import random
import asyncio

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.ai_core.trigger_bridge import ai_return

from .texts import GUESS_PROMPTS, ROULETTE_BANG, ROULETTE_SAFE
from .shared import reply, has_pm, allowed, game_sv
from .xf_config import get_int, get_bool
from .utils.events import sender_name
from .utils.helpers import clamp, human_duration

DICE_PATTERN = re.compile(r'^(\d{1,2})d(\d{1,6})$')
GUESS_RANGE = 100
GUESS_TIMEOUT = 180
ROULETTE_CHAMBER = 6

RPS_BEATS = {'石头': '剪刀', '剪刀': '布', '布': '石头'}
RPS_ALIAS = {
    '石头': '石头',
    '拳头': '石头',
    'rock': '石头',
    '剪刀': '剪刀',
    'scissors': '剪刀',
    '布': '布',
    'paper': '布',
}

DICE_DOC = """掷骰子，可以指定最大点数或 NdM 写法。
当用户说"掷骰子""roll 一下""随机一个数"时调用。

Args:
    text: 可留空（默认 1-100）。可以是最大点数如 "6"、"100"，也可以是 "2d6"（两颗六面骰之和）
"""

RPS_DOC = """玩一局石头剪刀布，和机器人比胜负。
当用户说"石头剪刀布""来猜拳"时调用。

Args:
    text: 出拳，必须是 石头 / 剪刀 / 布 之一。例如 "石头"
"""

GUESS_DOC = """在群里开始一局猜数字小游戏（1-100，群里任何人都可以猜）。
当用户说"猜数字""玩个猜数字"时调用。

Args:
    text: 无需参数，留空即可
"""

ROULETTE_DOC = """玩一局俄罗斯轮盘：1/6 概率被随机禁言一段时间。
当用户说"俄罗斯轮盘""玩轮盘""开一枪"时调用，仅在群里有效。

Args:
    text: 可留空（打自己）；也可以 @ 一个人让他挨枪
"""


@game_sv.on_command(
    ('掷骰子', '骰子', 'roll'),
    to_ai=DICE_DOC,
    covers=['掷骰子', '随机数', '骰子'],
    aliases=['今日老婆·掷骰子'],
)
async def roll_dice(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_dice_enable'):
        return

    text = ev.text.strip().lower().replace(' ', '')
    max_value = get_int('xf_dice_max') or 100

    matched = DICE_PATTERN.match(text)
    if matched is not None:
        count, faces = int(matched.group(1)), int(matched.group(2))
        if count < 1 or faces < 2:
            return await reply(bot, '骰子写法不对哦，例如：掷骰子 2d6')
        rolls = [random.randint(1, faces) for _ in range(count)]
        total = sum(rolls)
        detail = ' + '.join(str(value) for value in rolls)
        await bot.send(f'🎲 {count}d{faces}：{detail} = {total}')
        ai_return(f'掷骰子 {count}d{faces} 结果为 {total}（明细 {detail}）')
        return

    if text:
        if not text.isdigit():
            return await reply(bot, '请输入一个数字，例如：掷骰子 100')
        max_value = clamp(int(text), 2, get_int('xf_dice_max') or 1000000)

    value = random.randint(1, max_value)
    await bot.send(f'🎲 {sender_name(ev)} 掷出了 {value}（1-{max_value}）')
    ai_return(f'掷骰子 1-{max_value} 得到 {value}')


@game_sv.on_command(
    ('石头剪刀布', '猜拳', 'rps'),
    to_ai=RPS_DOC,
    covers=['石头剪刀布', '猜拳', '划拳'],
    aliases=['今日老婆·石头剪刀布'],
)
async def rock_paper_scissors(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_rps_enable'):
        return

    raw = ev.text.strip().lower()
    user_choice = RPS_ALIAS[raw] if raw in RPS_ALIAS else None
    if user_choice is None:
        return await reply(bot, '请出拳：石头 / 剪刀 / 布，例如：石头剪刀布 石头')

    bot_choice = random.choice(('石头', '剪刀', '布'))
    if user_choice == bot_choice:
        result = '平局！'
    elif RPS_BEATS[user_choice] == bot_choice:
        result = '你赢了！'
    else:
        result = '你输了～'
    await bot.send(f'✊ 你出【{user_choice}】，我出【{bot_choice}】：{result}')
    ai_return(f'石头剪刀布：用户 {user_choice} vs 机器人 {bot_choice}，{result}')


@game_sv.on_command(
    ('猜数字', '开始猜数字'),
    to_ai=GUESS_DOC,
    covers=['猜数字', '猜数游戏'],
    aliases=['今日老婆·猜数字'],
)
async def guess_number(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_guess_enable'):
        return
    if ev.group_id is None:
        return await reply(bot, '猜数字要在群里玩哦～')

    answer = random.randint(1, GUESS_RANGE)
    prompt = random.choice(GUESS_PROMPTS)
    await bot.send(f'{prompt}\n我想好了一个 1-{GUESS_RANGE} 的数字，直接发数字来猜。发【结束猜数字】可以中止。')

    attempts = 0
    try:
        async with asyncio.timeout(GUESS_TIMEOUT):
            while True:
                resp = await bot.receive_mutiply_resp()
                if resp is None:
                    return await reply(bot, f'没有人继续猜了，答案是 {answer}。')
                text = resp.text.strip()
                if text in ('结束猜数字', '结束', '不玩了'):
                    return await reply(bot, f'好吧，答案是 {answer}，下次再玩～')
                if not text.isdigit():
                    continue
                attempts += 1
                value = int(text)
                if value == answer:
                    return await reply(bot, f'🎉 {sender_name(resp)} 猜中了！答案就是 {answer}（第 {attempts} 次）')
                await bot.send('太小了，再大一点～' if value < answer else '太大了，再小一点～')
    except TimeoutError:
        await bot.send(f'时间到啦，没有人猜出来，答案是 {answer}。')


@game_sv.on_command(
    ('俄罗斯轮盘', '轮盘', '开一枪'),
    to_ai=ROULETTE_DOC,
    covers=['俄罗斯轮盘', '轮盘游戏', '随机禁言'],
    aliases=['今日老婆·俄罗斯轮盘'],
)
async def russian_roulette(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_roulette_enable'):
        return
    if not has_pm(ev, get_int('xf_roulette_pm')):
        return await reply(bot, '你的权限还不够玩轮盘哦～')
    if ev.group_id is None:
        return await reply(bot, '俄罗斯轮盘只能在群里玩哦～')

    target = ev.at or ev.user_id
    hit = random.randint(1, ROULETTE_CHAMBER) == 1
    if not hit:
        message = random.choice(ROULETTE_SAFE)
        await bot.send(f'🔫 {message}（第 {random.randint(2, ROULETTE_CHAMBER)} 个弹巢是空的）')
        ai_return(f'俄罗斯轮盘：这次是空枪，没有被禁言。{message}')
        return

    low = get_int('xf_roulette_min')
    high = max(low, get_int('xf_roulette_max'))
    duration = random.randint(max(1, low), max(1, high))
    await bot.send(f'🔫 {random.choice(ROULETTE_BANG)} 禁言 {human_duration(duration)}。')
    await bot.ban(target, ev.group_id, duration=duration)
    ai_return(f'俄罗斯轮盘：中枪了，已禁言 {target} {duration} 秒。')
