"""今日老婆积分操作：余额查询与扣减，直接使用合并进来的娱乐功能数据表。

积分由签到功能写入，所有消费点动作（换老婆、再抢、指定、锁定、赠送二手）统一走
这里的接口，便于集中处理「积分不足」的降级提示。
"""

from __future__ import annotations

from .fun.models import XfPointRecord


async def _get_balance(user_id: str, bot_id: str) -> int:
    """查询用户积分余额，无记录时返回 0。"""
    record = await XfPointRecord.get_record(user_id, bot_id)
    return record.points if record is not None else 0


async def _spend_points(user_id: str, bot_id: str, cost: int) -> bool:
    """扣减积分，余额不足时返回 False。"""
    return await XfPointRecord.spend(user_id, bot_id, cost)
