"""今日老婆积分发放规则：签到与打卡共用一个「每天每来源一次」的发放入口。

应发分数 = 基础分 + 连签/连打卡加成（加成封顶为基础分 3 倍，由 sign_points 计算）。
连签加成不会被裁剪，只限制「同一来源每天只发一次」——否则用免签道具重置签到
就能重复领取当天积分。
"""

from __future__ import annotations

from .models import XfPointRecord, XfPointGrantRecord
from .utils.helpers import today_str

SOURCE_SIGN = 'sign'
SOURCE_LUCK = 'luck'


async def granted_today(user_id: str, bot_id: str, source: str) -> int:
    return await XfPointGrantRecord.granted_of_day(user_id, bot_id, today_str(), source)


async def grant_daily_points(user_id: str, bot_id: str, source: str, amount: int) -> int:
    """每个来源每天只发一次积分，返回实发数量。

    `amount` 已包含连签加成，因此不做裁剪；重复触发（如免签卡重置签到后再签）
    返回 0，签到/打卡本身仍然成功，只是不再加分。
    """
    if amount <= 0:
        return 0
    day = today_str()
    granted = await XfPointGrantRecord.granted_of_day(user_id, bot_id, day, source)
    if granted > 0:
        return 0
    await XfPointRecord.add_points(user_id, bot_id, amount)
    await XfPointGrantRecord.grant(user_id, bot_id, day, source, amount)
    return amount
