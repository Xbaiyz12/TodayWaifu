"""积分商城：看商品、查余额、兑换（每人每件商品每天限兑一次）。"""

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.ai_core.trigger_bridge import ai_return

from .models import XfSignRecord, XfPointRecord, XfExchangeRecord
from .shared import reply, allowed, sign_sv
from .xf_config import get_bool, get_str_list
from .utils.events import sender_name
from .utils.helpers import today_str
from .utils.calendar_logic import ShopItem, parse_shop_item

SHOP_DOC = """查看积分商城的商品列表与价格。
当用户问"积分商城有什么""积分能换什么"时调用。

Args:
    text: 无需参数，留空即可
"""

POINTS_DOC = """查看用户自己的积分余额。
当用户问"我有多少积分""查积分""积分余额"时调用。

Args:
    text: 无需参数，留空即可
"""

REDEEM_DOC = """用积分兑换商城里的商品。
当用户说"我要兑换 xxx""用积分换一件"时调用。

Args:
    text: 商品名称，可以与商城里的名字部分匹配。例如 "今日免签"、"摸摸头"
"""


def shop_items() -> list[ShopItem]:
    items: list[ShopItem] = []
    for raw in get_str_list('xf_shop_items'):
        item = parse_shop_item(raw)
        if item is not None:
            items.append(item)
    return items


def _match_item(query: str, items: list[ShopItem]) -> ShopItem | None:
    key = query.strip()
    if not key:
        return None
    for item in items:
        if item.name == key:
            return item
    for item in items:
        if key in item.name:
            return item
    return None


async def _balance(user_id: str, bot_id: str) -> int:
    record = await XfPointRecord.get_record(user_id, bot_id)
    return record.points if record is not None else 0


@sign_sv.on_command(
    ('积分商城', '商城'),
    to_ai=SHOP_DOC,
    covers=['积分商城', '积分兑换什么', '商城列表'],
    aliases=['今日老婆·积分商城'],
)
async def shop_list(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_shop_enable'):
        return

    items = shop_items()
    balance = await _balance(ev.user_id, ev.bot_id)
    if not items:
        return await reply(bot, '商城还没有上架商品，可以让主人去网页控制台配置【商城商品】。')

    lines = [f'🛒 今日老婆积分商城（你的积分：{balance}）']
    for index, item in enumerate(items, start=1):
        desc = f' —— {item.desc}' if item.desc else ''
        lines.append(f'{index}. {item.name}（{item.cost} 分）{desc}')
    lines.append('发送【兑换 商品名】即可兑换，每人每件每天限一次。')
    await bot.send('\n'.join(lines))
    ai_return(
        f'【积分商城】共 {len(items)} 件商品；用户当前 {balance} 积分：'
        + '、'.join(f'{i.name}({i.cost})' for i in items)
    )


@sign_sv.on_command(
    ('查询积分', '我的积分', '积分余额'),
    to_ai=POINTS_DOC,
    covers=['查询积分', '积分余额', '我有多少积分'],
    aliases=['今日老婆·积分余额'],
)
async def query_points(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_points_enable'):
        return
    record = await XfPointRecord.get_record(ev.user_id, ev.bot_id)
    if record is None:
        return await reply(bot, '你还没有积分记录哦，先发【签到】攒一点吧～')
    await bot.send(
        f'💰 {sender_name(ev)} 的积分\n当前余额：{record.points}\n累计获得：{record.earned}\n累计消耗：{record.spent}'
    )
    ai_return(f'【积分余额】{sender_name(ev)}：{record.points}（累计获得 {record.earned}，消耗 {record.spent}）')


@sign_sv.on_command(
    '兑换',
    to_ai=REDEEM_DOC,
    covers=['兑换积分商品', '积分兑换'],
    aliases=['今日老婆·兑换'],
)
async def redeem(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_shop_enable'):
        return

    items = shop_items()
    item = _match_item(ev.text, items)
    if item is None:
        return await reply(bot, '商城没有这件商品哦，发【积分商城】看看有什么可以换的。')

    date = today_str()
    used = await XfExchangeRecord.count_today(ev.user_id, ev.bot_id, item.name, date)
    if used >= 1:
        return await reply(bot, f'今天已经兑换过【{item.name}】啦，明天再来～')

    balance = await _balance(ev.user_id, ev.bot_id)
    if balance < item.cost:
        return await reply(bot, f'积分不够哦，【{item.name}】需要 {item.cost} 分，你还有 {balance} 分。')

    spent = await XfPointRecord.spend(ev.user_id, ev.bot_id, item.cost)
    if not spent:
        return await reply(bot, '兑换失败，可能是积分刚刚被用掉了，稍后再试试。')

    await XfExchangeRecord.add(
        user_id=ev.user_id,
        bot_id=ev.bot_id,
        group_id=ev.group_id or '',
        item=item.name,
        cost=item.cost,
        date=date,
    )
    balance = await _balance(ev.user_id, ev.bot_id)

    extra = ''
    if '免签' in item.name:
        dropped = await XfSignRecord.drop_day(ev.user_id, ev.bot_id, date)
        extra = '\n今天已重置，可以再签到一次啦！' if dropped else '\n今天本来就没签到，免签机会先留着～'

    await bot.send(f'✅ 兑换成功：【{item.name}】-{item.cost} 分，剩余 {balance} 分{extra}')
    ai_return(f'【兑换成功】{sender_name(ev)} 用 {item.cost} 积分兑换了「{item.name}」，剩余 {balance} 积分')
