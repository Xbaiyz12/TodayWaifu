"""今日老婆 公共层：SV 实例、主题定义、图库访问器与消息背景缓存。"""

from typing import Literal
from pathlib import Path
from dataclasses import dataclass

from PIL import Image

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event, Message

from .texts import pick_kou_line, pick_deer_line
from .xf_config import IntKey, StrKey, BoolKey, get_int, get_str, get_bool, is_plugin_allowed
from .utils.paths import ICON_PATH, DEFAULT_LUCK_BG_DIR, DEFAULT_SIGN_BG_DIR
from .utils.image_lib import ImageLibrary, open_image

# ==================== SV 实例 ====================

luck_sv = SV(name='今日老婆-打卡运势', pm=6, area='ALL')
gif_sv = SV(name='今日老婆-GIF工具', pm=6, area='ALL')
calendar_sv = SV(name='今日老婆-鹿扣日历', pm=6, area='ALL')
sign_sv = SV(name='今日老婆-签到积分', pm=6, area='ALL')
tarot_sv = SV(name='今日老婆-塔罗占卜', pm=6, area='ALL')
game_sv = SV(name='今日老婆-群聊游戏', pm=6, area='ALL')
greet_sv = SV(name='今日老婆-问候推送', pm=6, area='ALL')

ThemeKey = Literal['deer', 'kou']


@dataclass(frozen=True)
class Theme:
    """鹿 / 扣 两套完全平行的人品日历。"""

    key: ThemeKey
    word: str
    emoji: tuple[str, ...]
    name_key: StrKey
    cap_key: IntKey
    enable_key: BoolKey
    icon_file: str


DEER_THEME = Theme(
    key='deer',
    word='鹿',
    emoji=('🦌',),
    name_key='xf_deer_name',
    cap_key='xf_deer_daily_cap',
    enable_key='xf_deer_enable',
    icon_file='deer.png',
)

KOU_THEME = Theme(
    key='kou',
    word='扣',
    emoji=('扣', '🤏'),
    name_key='xf_kou_name',
    cap_key='xf_kou_daily_cap',
    enable_key='xf_kou_enable',
    icon_file='kou.png',
)

THEMES: tuple[Theme, ...] = (DEER_THEME, KOU_THEME)


def theme_name(theme: Theme) -> str:
    return get_str(theme.name_key).strip() or theme.word


def theme_enabled(theme: Theme) -> bool:
    return get_bool(theme.enable_key)


def theme_cap(theme: Theme) -> int:
    return get_int(theme.cap_key)


def theme_line(theme: Theme) -> str:
    return pick_kou_line() if theme.key == 'kou' else pick_deer_line()


def theme_icon(theme: Theme) -> Image.Image | None:
    path = ICON_PATH / theme.icon_file
    if not path.is_file():
        return None
    return open_image(path)


# ==================== 图库 ====================

_luck_library = ImageLibrary(DEFAULT_LUCK_BG_DIR)
_sign_library = ImageLibrary(DEFAULT_SIGN_BG_DIR, landscape_only=True)


def luck_library() -> ImageLibrary:
    """打卡面板图库：配置留空时用鸣潮自定义面板图目录。"""
    configured = get_str('xf_luck_bg_dir').strip()
    _luck_library.set_root(Path(configured) if configured else DEFAULT_LUCK_BG_DIR)
    return _luck_library


def sign_library() -> ImageLibrary:
    """签到横图库：配置留空时用鸣潮自定义名片背景目录。"""
    configured = get_str('xf_sign_bg_dir').strip()
    _sign_library.set_root(Path(configured) if configured else DEFAULT_SIGN_BG_DIR)
    return _sign_library


# ==================== 守卫 ====================


async def allowed(ev: Event) -> bool:
    """总开关 + 黑白名单，不通过时静默（避免在无关群里刷屏）。"""
    return is_plugin_allowed(ev.group_id, ev.user_id)


Sendable = Message | list[Message] | str | bytes | list[str]


async def reply(bot: Bot, message: Sendable) -> None:
    """触发器统一收尾：Bot.send 返回的是出站消息 id，不是触发器的返回值。"""
    await bot.send(message)


def has_pm(ev: Event, needed: int) -> bool:
    return ev.user_pm <= needed


# ==================== 消息 → 背景图 缓存 ====================

_MSG_BG_CACHE: dict[str, Path] = {}
_MAX_CACHE = 1000


def remember_bg(message_ids: list[str] | None, path: Path | None) -> None:
    if not message_ids or path is None:
        return
    for message_id in message_ids:
        _MSG_BG_CACHE[message_id] = path
    while len(_MSG_BG_CACHE) > _MAX_CACHE:
        # FIFO 淘汰：next(iter(...)) 拿到的键一定存在，直接删
        del _MSG_BG_CACHE[next(iter(_MSG_BG_CACHE))]


def recall_bg(message_id: str | None) -> Path | None:
    if not message_id:
        return None
    return _MSG_BG_CACHE[message_id] if message_id in _MSG_BG_CACHE else None
