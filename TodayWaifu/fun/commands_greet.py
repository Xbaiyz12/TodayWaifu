"""早安 / 晚安问候与定时推送订阅。"""

import random

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe
from gsuid_core.ai_core.trigger_bridge import ai_return

from .texts import GREET_NIGHT, GREET_MORNING
from .shared import allowed, greet_sv
from .xf_config import get_bool
from .utils.events import sender_name

# 任务名是 gs_subscribe 里的落库标识，改名会让老用户的订阅失效，故保留旧值
MORNING_TASK = '小白娱乐屋早安'
NIGHT_TASK = '小白娱乐屋晚安'

MORNING_DOC = """跟用户说一声早安（随机祝福语）。
当用户说"早安""早上好"时调用。

Args:
    text: 无需参数，留空即可
"""

NIGHT_DOC = """跟用户说一声晚安（随机祝福语）。
当用户说"晚安""晚安啦"时调用。

Args:
    text: 无需参数，留空即可
"""

SUBSCRIBE_DOC = """订阅或取消本群的每日早安/晚安定时推送。
当用户说"订阅早安""每天早上发一句""取消订阅晚安"时调用。

Args:
    text: 无需参数，留空即可；指令本身就是【订阅早安】/【订阅晚安】/【取消订阅早安】/【取消订阅晚安】
"""


def _is_morning(command: str) -> bool:
    return '早' in command


async def _dispatch_greet(bot: Bot, ev: Event, morning: bool) -> None:
    if not await allowed(ev) or not get_bool('xf_greet_enable'):
        return
    pool = GREET_MORNING if morning else GREET_NIGHT
    word = '早安' if morning else '晚安'
    line = random.choice(pool)
    await bot.send(f'{sender_name(ev)}，{line}')
    ai_return(f'已向 {sender_name(ev)} 说了一声{word}：{line}')


@greet_sv.on_command(
    ('早安', '早上好', '早哇'),
    to_ai=MORNING_DOC,
    covers=['早安', '早上好'],
    aliases=['今日老婆·早安'],
)
async def greet_morning(bot: Bot, ev: Event) -> None:
    await _dispatch_greet(bot, ev, True)


@greet_sv.on_command(
    ('晚安',),
    to_ai=NIGHT_DOC,
    covers=['晚安', '晚安啦'],
    aliases=['今日老婆·晚安'],
)
async def greet_night(bot: Bot, ev: Event) -> None:
    await _dispatch_greet(bot, ev, False)


@greet_sv.on_command(
    ('订阅早安', '订阅晚安'),
    to_ai=SUBSCRIBE_DOC,
    covers=['订阅早安', '订阅晚安', '定时问候'],
    aliases=['今日老婆·订阅问候'],
)
async def subscribe_greet(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_greet_push_enable'):
        return
    morning = _is_morning(ev.command)
    task = MORNING_TASK if morning else NIGHT_TASK
    word = '早安' if morning else '晚安'
    await gs_subscribe.add_subscribe(
        subscribe_type='session',
        task_name=task,
        event=ev,
    )
    await bot.send(f'✅ 已订阅每日{word}，到点我会来打招呼的（时间可在网页控制台调整）。')
    ai_return(f'已让当前会话订阅每日{word}推送。')


@greet_sv.on_command(
    ('取消订阅早安', '取消订阅晚安'),
    to_ai=SUBSCRIBE_DOC,
    covers=['取消订阅早安', '取消订阅晚安', '停止定时问候'],
    aliases=['今日老婆·取消订阅问候'],
)
async def unsubscribe_greet(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_greet_push_enable'):
        return
    morning = _is_morning(ev.command)
    task = MORNING_TASK if morning else NIGHT_TASK
    word = '早安' if morning else '晚安'
    await gs_subscribe.delete_subscribe('session', task, ev)
    await bot.send(f'已取消每日{word}推送。')
    ai_return(f'已取消当前会话的每日{word}推送。')
