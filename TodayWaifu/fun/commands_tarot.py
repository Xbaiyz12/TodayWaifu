"""塔罗占卜：韦特塔罗 78 张牌库 + 本地出图（单张 / 三张牌阵）。"""

import random

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.utils.cooldown import cooldown_tracker
from gsuid_core.ai_core.trigger_bridge import ai_return

from .texts import TAROT_INTROS
from .shared import reply, allowed, tarot_sv
from .xf_config import BoolKey, get_int, get_bool
from .tarot_data import TAROT_CARDS
from .utils.events import sender_name
from .utils.render.tarot_card import TarotDraw, render_tarot_card

REVERSED_RATE = 0.35

SINGLE_DOC = """抽一张塔罗牌回答用户的问题（单张牌意）。
当用户说"抽张塔罗""塔罗牌看看""给我抽一张牌"时调用。

Args:
    text: 用户想问的问题，可留空。例如 "这次抽卡会出货吗"、"我该不该换工作"
"""

THREE_DOC = """用三张牌牌阵占卜用户的问题（过去/现在/未来式解读素材）。
当用户说"占卜一下""三张牌""帮我算一卦塔罗"时调用。

Args:
    text: 用户想问的问题，可留空。例如 "这段感情会怎么样"
"""


def _draw_one() -> TarotDraw:
    card = random.choice(TAROT_CARDS)
    reversed_card = random.random() < REVERSED_RATE
    return TarotDraw(
        name=card['name'],
        name_en=card['name_en'],
        arcana=card['arcana'],
        suit=card['suit'],
        number=card['number'],
        reversed=reversed_card,
        meaning=card['reversed'] if reversed_card else card['upright'],
        keywords=card['keywords'],
    )


def _summary(draws: list[TarotDraw]) -> str:
    parts = []
    for card in draws:
        position = '逆位' if card['reversed'] else '正位'
        parts.append(f'{card["name"]}（{position}）：{card["meaning"]}')
    return '；'.join(parts)


async def _send_tarot(bot: Bot, ev: Event, count: int, enable_key: BoolKey) -> None:
    if not await allowed(ev) or not get_bool(enable_key):
        return

    cooldown = get_int('xf_tarot_cooldown')
    if cooldown > 0 and cooldown_tracker.is_on_cooldown(f'xf_tarot:{ev.user_id}', cooldown):
        return await reply(bot, f'稍微等一下再抽吧，{cooldown} 秒后才能再占卜一次～')

    question = ev.text.strip()
    draws = [_draw_one() for _ in range(count)]
    intro = random.choice(TAROT_INTROS)
    card = await render_tarot_card(question, intro, draws)
    await bot.send(MessageSegment.image(card))
    ai_return(f'【塔罗占卜】{sender_name(ev)} 问「{question or "未指定"}」：{_summary(draws)}')


@tarot_sv.on_command(
    ('塔罗牌', '彩虹塔罗牌'),
    to_ai=SINGLE_DOC,
    covers=['塔罗牌', '抽塔罗', '占卜单张'],
    aliases=['今日老婆·塔罗牌'],
)
async def tarot_single(bot: Bot, ev: Event) -> None:
    await _send_tarot(bot, ev, 1, 'xf_tarot_enable')


@tarot_sv.on_command(
    '占卜',
    to_ai=THREE_DOC,
    covers=['塔罗占卜', '三张牌', '算一卦'],
    aliases=['今日老婆·塔罗三张'],
)
async def tarot_three(bot: Bot, ev: Event) -> None:
    await _send_tarot(bot, ev, 3, 'xf_tarot_three_enable')
