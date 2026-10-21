"""赠送积分：把积分转给指定用户，扣减与入账在同一事务里完成。

积分不因为转账而凭空产生，接收方拿到的额度不计入「每指令每日上限」——那是给
签到、打卡这类产出积分的指令用的限额，转赠只是存量转移。
"""

import re

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.ai_core.trigger_bridge import ai_return

from .models import XfPointRecord
from .shared import reply, allowed, sign_sv
from .xf_config import get_bool
from .utils.events import sender_name

TRANSFER_COMMANDS = ('赠送积分', '转赠积分', '送积分')

TRANSFER_DOC = """把自己的积分赠送给群友。
当用户说"赠送积分""转赠积分""送积分给某人"时调用。

Args:
    text: 对方与数量，例如：@某人 50 或 123456789 50
"""

_AT_CQ = re.compile(r'\[CQ:at,[^\]]*\]')
_AT_TAG = re.compile(r'<(?:qqbot-)?at[^>]*>')
_NUMBER = re.compile(r'\d+')


def _parse_transfer(ev: Event) -> tuple[str | None, int | None]:
    """解析目标与数量：优先用结构化 @，否则要求「对方ID 数量」两段文本。"""
    text = str(ev.text or '')
    cleaned = _AT_TAG.sub(' ', _AT_CQ.sub(' ', text))
    numbers = _NUMBER.findall(cleaned)

    at = ev.at if ev.at else (next(iter(ev.at_list), '') if ev.at_list else '')
    if at:
        return str(at).strip(), int(numbers[0]) if numbers else None

    # 无 @ 时不能把数量当目标：QQ 号至少 5 位，且必须同时给出数量
    if len(numbers) >= 2 and len(numbers[0]) >= 5:
        return numbers[0], int(numbers[1])
    return None, None


@sign_sv.on_command(
    TRANSFER_COMMANDS,
    to_ai=TRANSFER_DOC,
    covers=['赠送积分', '转赠积分', '送积分给群友'],
    aliases=['今日老婆·赠送积分'],
)
async def transfer_points(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_points_enable'):
        return

    target_user_id, amount = _parse_transfer(ev)
    if target_user_id is None or amount is None:
        return await reply(bot, '用法：赠送积分 @对方 数量，例如：赠送积分 @小明 50')
    if target_user_id == ev.user_id:
        return await reply(bot, '不能把积分送给自己哦～')
    if amount <= 0:
        return await reply(bot, '赠送数量必须是正整数。')

    sender = await XfPointRecord.get_record(ev.user_id, ev.bot_id)
    balance = sender.points if sender is not None else 0
    if balance < amount:
        return await reply(bot, f'积分不够哦，你当前有 {balance} 分，想赠送 {amount} 分。')

    transferred = await XfPointRecord.transfer(ev.user_id, target_user_id, ev.bot_id, amount)
    if not transferred:
        return await reply(bot, '赠送失败：积分可能刚刚被用掉了，稍后再试试。')

    left = await XfPointRecord.get_record(ev.user_id, ev.bot_id)
    received = await XfPointRecord.get_record(target_user_id, ev.bot_id)
    left_balance = left.points if left is not None else 0
    received_balance = received.points if received is not None else 0
    await bot.send(
        f'✅ 已赠送 {amount} 积分给 {target_user_id}\n你的余额：{left_balance}\n对方余额：{received_balance}'
    )
    ai_return(
        f'【赠送积分】{sender_name(ev)} 赠送 {amount} 积分给 {target_user_id}，'
        f'赠送方余额 {left_balance}，接收方余额 {received_balance}'
    )
