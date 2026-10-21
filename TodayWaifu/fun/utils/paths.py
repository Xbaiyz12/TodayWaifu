"""今日老婆·娱乐功能路径常量。

运行时数据一律落在 data/TodayWaifu/entertainment/，不写插件代码目录；旧插件的
data/XbaiyzFun/ 只在 xf_config 里迁移配置，缓存可重新生成故不迁移。
"""

from pathlib import Path

from gsuid_core.data_store import get_res_path

# 内层包 plugins/TodayWaifu/TodayWaifu/fun/
PKG_ROOT = Path(__file__).resolve().parent.parent

# 随插件分发的只读素材（字体与鹿/扣图标）
RESOURCE_PATH = PKG_ROOT / 'resources'
FONT_PATH = RESOURCE_PATH / 'font'
ICON_PATH = RESOURCE_PATH / 'icon'

# 运行时数据根目录：data/TodayWaifu/entertainment/
XF_ROOT = get_res_path('TodayWaifu') / 'entertainment'
CACHE_PATH = XF_ROOT / 'cache'
AVATAR_CACHE_PATH = CACHE_PATH / 'avatar'

for _path in (CACHE_PATH, AVATAR_CACHE_PATH):
    _path.mkdir(parents=True, exist_ok=True)

# 鸣潮插件的数据目录，打卡面板图与签到横图默认都从这里取
XWUID_ROOT = get_res_path() / 'XutheringWavesUID'
DEFAULT_LUCK_BG_DIR = XWUID_ROOT / 'custom_role_pile'
DEFAULT_SIGN_BG_DIR = XWUID_ROOT / 'custom_mr_bg'
