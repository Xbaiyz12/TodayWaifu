"""定时任务：给订阅了早安/晚安推送的会话发问候。

时间从配置读取，所以改时间不用重启；每 5 分钟检查一次，命中当天目标时间后当天只推一次。
"""

import random
import datetime

from gsuid_core.aps import scheduler
from gsuid_core.logger import logger
from gsuid_core.subscribe import gs_subscribe

from .texts import GREET_NIGHT, GREET_MORNING
from .xf_config import get_bool, get_time
from .commands_greet import NIGHT_TASK, MORNING_TASK

PUSH_WINDOW_MINUTES = 30
_pushed: dict[str, str] = {}


def _claim_push(kind: str, now: datetime.datetime) -> bool:
    """到点且今天还没推过就占位，返回 True 表示本次该推。"""
    hour, minute = get_time('xf_greet_morning' if kind == 'morning' else 'xf_greet_night')
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = (now - target).total_seconds()
    if delta < 0 or delta > PUSH_WINDOW_MINUTES * 60:
        return False

    key = f'{kind}:{now.date().isoformat()}'
    if key in _pushed:
        return False
    _pushed[key] = now.isoformat()

    # 只留当天的占位，避免长期运行把内存撑大
    today_prefix = now.date().isoformat()
    for stored in list(_pushed):
        if not stored.endswith(today_prefix):
            del _pushed[stored]
    return True


async def _push_greet(kind: str, task_name: str, pool: list[str]) -> None:
    subs = await gs_subscribe.get_subscribe(task_name=task_name)
    if not subs:
        return
    for sub in subs:
        await sub.send(reply=random.choice(pool), unsuported_platform=True)
    logger.info(f'[今日老婆·问候] 已推送 {kind} 给 {len(subs)} 个会话')


@scheduler.scheduled_job('interval', minutes=5)
async def greet_push_job() -> None:
    if not get_bool('xf_greet_push_enable'):
        return

    now = datetime.datetime.now()
    try:
        if _claim_push('morning', now):
            await _push_greet('morning', MORNING_TASK, GREET_MORNING)
        if _claim_push('night', now):
            await _push_greet('night', NIGHT_TASK, GREET_NIGHT)
    except Exception:
        # APScheduler 会吞掉定时任务的异常，这里必须自己记下来
        logger.exception('[今日老婆·问候] 定时推送失败')
