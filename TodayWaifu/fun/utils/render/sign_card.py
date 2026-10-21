"""每日签到横图：本地横图做底，叠一层暗色渐变保证文字清晰。

半透明元素画在独立 overlay 上再 alpha_composite：直接画在底图上会把像素的 alpha
改小，转 JPEG 时被当成不透明白色，卡片会整片变白。
"""

from typing import TypedDict
from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.pool import to_thread

from ..fonts import title_font, number_font
from ..image_lib import cover_crop, open_image, image_bytes, circle_image, rounded_rect

WIDTH = 1200
HEIGHT = 675


class SignCardData(TypedDict):
    """签到横图上的全部文字数据。"""

    name: str
    date_label: str
    streak: int
    total_days: int
    gained: int
    balance: int
    blessing: str
    title: str


def _fallback_background() -> Image.Image:
    image = Image.new('RGBA', (WIDTH, HEIGHT), (238, 247, 252, 255))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / (HEIGHT - 1)
        color = (
            int(238 - 26 * ratio),
            int(247 - 12 * ratio),
            int(252 - 8 * ratio),
            255,
        )
        draw.line([(0, y), (WIDTH, y)], fill=color)
    return image


def _render_sync(bg_path: Path | None, avatar: Image.Image | None, data: SignCardData) -> bytes:
    canvas = _fallback_background()
    if bg_path is not None:
        background = open_image(bg_path)
        if background is not None:
            canvas = cover_crop(background, WIDTH, HEIGHT)

    veil = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    veil_draw = ImageDraw.Draw(veil)
    for y in range(HEIGHT):
        # 上方轻、下方重：文字都落在下半部，保证对比度
        alpha = int(40 + 150 * (y / HEIGHT))
        veil_draw.line([(0, y), (WIDTH, y)], fill=(12, 24, 36, alpha))
    canvas = Image.alpha_composite(canvas, veil)

    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    title = title_font(52)
    name_font = title_font(38)
    label = title_font(24)
    value = number_font(44)
    blessing = title_font(26)
    badge = title_font(22)

    draw.text((72, 56), '每日签到', font=title, fill=(255, 255, 255, 255))

    badge_box = draw.textbbox((0, 0), data['title'], font=badge)
    badge_width = int(badge_box[2] - badge_box[0]) + 44
    rounded_rect(
        draw,
        (WIDTH - 72 - badge_width, 62, WIDTH - 72, 62 + 52),
        26,
        (255, 255, 255, 70),
        (255, 255, 255, 200),
        2,
    )
    draw.text((WIDTH - 72 - badge_width + 22, 62 + 12), data['title'], font=badge, fill=(255, 255, 255, 255))

    avatar_size = 150
    avatar_x, avatar_y = 72, 210
    if avatar is not None:
        circle = circle_image(avatar, avatar_size)
        draw.ellipse(
            (avatar_x - 4, avatar_y - 4, avatar_x + avatar_size + 4, avatar_y + avatar_size + 4),
            fill=(255, 255, 255, 200),
        )
        overlay.paste(circle, (avatar_x, avatar_y), circle)
    else:
        draw.ellipse(
            (avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size),
            fill=(210, 222, 232, 200),
            outline=(255, 255, 255, 220),
            width=3,
        )

    text_x = avatar_x + avatar_size + 42
    draw.text((text_x, avatar_y + 12), data['name'], font=name_font, fill=(255, 255, 255, 255))
    draw.text((text_x, avatar_y + 74), data['date_label'], font=label, fill=(196, 226, 240, 255))

    stats: tuple[tuple[str, str], ...] = (
        ('连续签到', f'{data["streak"]} 天'),
        ('累计签到', f'{data["total_days"]} 天'),
        ('本次积分', f'+{data["gained"]}'),
        ('积分余额', str(data['balance'])),
    )
    stat_x = 700
    stat_y = 200
    for index, (stat_label, stat_value) in enumerate(stats):
        row, column = divmod(index, 2)
        box_x = stat_x + column * 240
        box_y = stat_y + row * 110
        rounded_rect(draw, (box_x, box_y, box_x + 214, box_y + 90), 18, (255, 255, 255, 60), (255, 255, 255, 150), 1)
        draw.text((box_x + 20, box_y + 12), stat_label, font=label, fill=(214, 236, 246, 255))
        draw.text((box_x + 20, box_y + 40), stat_value, font=value, fill=(255, 255, 255, 255))

    rounded_rect(draw, (72, 520, WIDTH - 72, 604), 22, (255, 255, 255, 56), (255, 255, 255, 140), 1)
    draw.text((96, 546), data['blessing'], font=blessing, fill=(255, 255, 255, 255))

    canvas = Image.alpha_composite(canvas, overlay)
    return image_bytes(canvas, 'JPEG')


@to_thread
def render_sign_card(bg_path: Path | None, avatar: Image.Image | None, data: SignCardData) -> bytes:
    return _render_sync(bg_path, avatar, data)
