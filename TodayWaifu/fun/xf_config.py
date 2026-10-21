"""今日老婆·娱乐功能配置读写封装。

框架 `get_config` 返回 Any，这里立即收敛成具体类型，业务侧只拿得到确定的类型。
"""

from typing import Literal

from gsuid_core.logger import logger
from gsuid_core.data_store import get_res_path
from gsuid_core.utils.plugins_config.gs_config import StringConfig

from .config_default import CONFIG_DEFAULT

# 运行时数据统一落在今日老婆目录：data/TodayWaifu/entertainment/
ENTERTAINMENT_ROOT = get_res_path('TodayWaifu') / 'entertainment'
CONFIG_PATH = ENTERTAINMENT_ROOT / 'config.json'
# StringConfig 构造时会直接以写模式打开配置文件，目录必须先就绪
ENTERTAINMENT_ROOT.mkdir(parents=True, exist_ok=True)

# 旧插件把配置写在 data/XbaiyzFun/config.json：首次加载时整体搬运，承接老用户的
# 自定义开关与商城商品；新位置已有文件说明用户在当前版本下改过配置，不得覆盖。
_LEGACY_CONFIG_PATH = get_res_path('XbaiyzFun') / 'config.json'
if _LEGACY_CONFIG_PATH.is_file() and not CONFIG_PATH.is_file():
    CONFIG_PATH.write_bytes(_LEGACY_CONFIG_PATH.read_bytes())

# 已下线的配置项会残留在文件里：StringConfig 不再渲染它们，但旧值仍占文件，这里在
# 实例化前一次性删除，避免控制台与导出的配置里留着无法编辑的历史键。
_LEGACY_KEYS_TO_REMOVE = ('xf_point_daily_cap',)
if CONFIG_PATH.is_file():
    import json

    _raw_config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    _removed_keys = [key for key in _LEGACY_KEYS_TO_REMOVE if key in _raw_config]
    for _key in _removed_keys:
        del _raw_config[_key]
    if _removed_keys:
        CONFIG_PATH.write_text(json.dumps(_raw_config, ensure_ascii=False, indent=4), encoding='utf-8')

_fun_config = StringConfig('今日老婆娱乐', CONFIG_PATH, CONFIG_DEFAULT)

# 以目录链接方式加载插件时 Path.resolve() 会跟踪到真实路径，使 plugin_name 自动推导
# 失败；显式回填确保控制台把配置页归属到今日老婆。
_fun_config.plugin_name = 'TodayWaifu'

BoolKey = Literal[
    'xf_enable',
    'xf_whitelist_enable',
    'xf_luck_enable',
    'xf_luck_rank_enable',
    'xf_extract_enable',
    'xf_gif_enable',
    'xf_gif_speed_enable',
    'xf_gif_split_enable',
    'xf_deer_enable',
    'xf_kou_enable',
    'xf_calendar_rank_enable',
    'xf_calendar_stats_enable',
    'xf_calendar_fix_enable',
    'xf_sign_enable',
    'xf_points_enable',
    'xf_shop_enable',
    'xf_tarot_enable',
    'xf_tarot_three_enable',
    'xf_dice_enable',
    'xf_rps_enable',
    'xf_guess_enable',
    'xf_roulette_enable',
    'xf_greet_enable',
    'xf_greet_push_enable',
]

IntKey = Literal[
    'xf_luck_retry_below',
    'xf_luck_rank_limit',
    'xf_gif_max_mb',
    'xf_gif_max_frames',
    'xf_deer_daily_cap',
    'xf_kou_daily_cap',
    'xf_calendar_fix_pm',
    'xf_sign_points',
    'xf_sign_streak_bonus',
    'xf_tarot_cooldown',
    'xf_dice_max',
    'xf_roulette_min',
    'xf_roulette_max',
    'xf_roulette_pm',
]

FloatKey = Literal['xf_gif_min_speed', 'xf_gif_max_speed']

StrKey = Literal['xf_luck_bg_dir', 'xf_deer_name', 'xf_kou_name', 'xf_sign_bg_dir']

ListKey = Literal['xf_whitelist', 'xf_blacklist', 'xf_shop_items']

TimeKey = Literal['xf_greet_morning', 'xf_greet_night']

ConfigKey = BoolKey | IntKey | FloatKey | StrKey | ListKey | TimeKey


def _raw(key: ConfigKey) -> object:
    value: object = _fun_config.get_config(key).data
    return value


def get_bool(key: BoolKey) -> bool:
    value = _raw(key)
    return value if isinstance(value, bool) else False


def get_int(key: IntKey) -> int:
    value = _raw(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def get_float(key: FloatKey) -> float:
    value = _raw(key)
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def get_str(key: StrKey) -> str:
    value = _raw(key)
    return value if isinstance(value, str) else ''


def get_str_list(key: ListKey) -> list[str]:
    value = _raw(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def get_time(key: TimeKey) -> tuple[int, int]:
    value = _raw(key)
    if isinstance(value, (tuple, list)) and len(value) == 2:
        hour, minute = value[0], value[1]
        if isinstance(hour, int) and isinstance(minute, int):
            return (hour, minute)
    return (0, 0)


def set_config(key: ConfigKey, value: bool | int | str | list[str]) -> bool:
    """写入并落盘；类型不匹配时框架会拒绝，这里必须把失败记下来而不是静默丢。"""
    ok = _fun_config.set_config(key, value)
    if not ok:
        logger.warning(f'[今日老婆·配置] 写入失败（类型不匹配）: {key}={value!r}')
    return ok


def is_plugin_allowed(group_id: str | None, user_id: str) -> bool:
    """总开关 + 黑白名单：黑名单优先；白名单里群号与用户号都认（命中其一即放行）。"""
    if not get_bool('xf_enable'):
        return False

    blacklist = get_str_list('xf_blacklist')
    if user_id in blacklist:
        return False
    if group_id is not None and blacklist and group_id in blacklist:
        return False

    if not get_bool('xf_whitelist_enable'):
        return True

    whitelist = get_str_list('xf_whitelist')
    return user_id in whitelist or (group_id is not None and group_id in whitelist)
