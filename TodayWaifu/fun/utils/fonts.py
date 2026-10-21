"""字体加载：优先用插件自带字体（保留原打卡模板观感），缺失时回退框架字体。"""

from PIL import ImageFont

from gsuid_core.utils.fonts.fonts import core_font

from .paths import FONT_PATH

TITLE_FONT_PATH = FONT_PATH / 'HYWenHei.ttf'
NUMBER_FONT_PATH = FONT_PATH / 'FangZhen.ttf'


def title_font(size: int) -> ImageFont.FreeTypeFont:
    if TITLE_FONT_PATH.is_file():
        return ImageFont.truetype(str(TITLE_FONT_PATH), size)
    return core_font(size)


def number_font(size: int) -> ImageFont.FreeTypeFont:
    """渐变艺术字用字体（原模板的方正字体）。"""
    if NUMBER_FONT_PATH.is_file():
        return ImageFont.truetype(str(NUMBER_FONT_PATH), size)
    return core_font(size)
