"""打卡运势卡片：沿用原 luck-plugin 的版式、配色与字体，只换成框架侧的字体加载。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.pool import to_thread

from ..fonts import title_font, number_font
from ...texts import BAND_LABELS
from ..image_lib import cover_crop, open_image, image_bytes, rounded_rect, gradient_text

WIDTH = 1200
HEIGHT = 1420
CONTENT_HEIGHT = 1330

COLOR_TEAL_DARK = (13, 120, 115, 255)
COLOR_TEAL_MUTED = (15, 118, 110, 240)
COLOR_BLUE_DARK = (3, 105, 161, 255)
COLOR_BLUE_MUTED = (14, 116, 144, 230)
COLOR_HIGHLIGHT = (2, 132, 199, 255)
COLOR_TIER = (217, 70, 239, 255)
COLOR_ACTIVE_FILL = (236, 72, 153, 235)

GRADIENT_START = (255, 0, 106)
GRADIENT_END = (106, 92, 255)


def _draw_text_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, ...],
) -> None:
    """白底卡片上的文字先描一层白，保证透光背景下依然清晰。"""
    draw.text((xy[0] + 1, xy[1] + 1), text, font=font, fill=(255, 255, 255, 180))
    draw.text(xy, text, font=font, fill=color)


def _render_sync(
    bg_path: Path | None,
    avatar_img: Image.Image | None,
    username: str,
    luck: int,
    tier_name: str,
    hint_text: str,
    quote_text: str,
    active_index: int,
    bg_id: str,
) -> bytes:
    canvas = Image.new('RGBA', (WIDTH, HEIGHT), (235, 238, 245, 255))

    if bg_path is not None:
        background = open_image(bg_path)
        if background is not None:
            canvas.paste(cover_crop(background, WIDTH, HEIGHT), (0, 0))

    tint = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    tint_draw = ImageDraw.Draw(tint)
    for y in range(HEIGHT):
        alpha = int(35 + 25 * (y / HEIGHT))
        tint_draw.line([(0, y), (WIDTH, y)], fill=(10, 15, 25, alpha))
    canvas = Image.alpha_composite(canvas, tint)

    title = title_font(50)
    card_title = title_font(34)
    card_body = title_font(28)
    card_desc = title_font(24)
    luck_number = number_font(110)
    quote = number_font(28)
    grid_sub = title_font(17)
    footer = title_font(20)

    glass = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glass)

    t_bbox = draw.textbbox((0, 0), '今日幸运值', font=title)
    t_width = t_bbox[2] - t_bbox[0]
    draw.text((WIDTH // 2 - t_width // 2 + 2, 47), '今日幸运值', font=title, fill=(0, 0, 0, 180))
    draw.text((WIDTH // 2 - t_width // 2, 45), '今日幸运值', font=title, fill=(255, 255, 255, 255))

    c_x1, c_y1, c_x2, c_y2 = 75, 125, 1125, 385
    rounded_rect(draw, (c_x1, c_y1, c_x2, c_y2), 36, (255, 255, 255, 130), (255, 255, 255, 210), 2)

    avatar_size = 160
    ax, ay = c_x1 + 45, c_y1 + 45
    if avatar_img is not None:
        scaled = cover_crop(avatar_img, avatar_size, avatar_size)
        mask = Image.new('L', (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        circle = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
        circle.paste(scaled, (0, 0), mask)
        draw.ellipse((ax - 3, ay - 3, ax + avatar_size + 3, ay + avatar_size + 3), fill=(255, 255, 255, 220))
        glass.paste(circle, (ax, ay), circle)
    else:
        draw.ellipse((ax, ay, ax + avatar_size, ay + avatar_size), fill=(210, 220, 235, 180))

    tx = ax + avatar_size + 45
    display_name = username if len(username) <= 16 else username[:15] + '...'
    _draw_text_shadow(draw, (tx, c_y1 + 46), f'✨ 你的名稱 :  {display_name}', card_title, COLOR_TEAL_DARK)
    _draw_text_shadow(draw, (tx, c_y1 + 108), f'✨ 你的幸运值 :  {luck} 分', card_body, COLOR_BLUE_DARK)
    draw.text((tx, c_y1 + 162), f'✨ 运势评级 :  {tier_name}', font=card_body, fill=COLOR_TIER)

    d_x1, d_y1, d_x2, d_y2 = 75, 410, 1125, 680
    rounded_rect(draw, (d_x1, d_y1, d_x2, d_y2), 30, (255, 255, 255, 130), (255, 255, 255, 210), 2)

    gradient = gradient_text(str(luck), luck_number, GRADIENT_START, GRADIENT_END)
    glass.paste(gradient, (d_x1 + 55, d_y1 + 50), gradient)
    draw.line([(d_x1 + 325, d_y1 + 35), (d_x1 + 325, d_y2 - 35)], fill=(255, 255, 255, 180), width=2)

    rx = d_x1 + 360
    _draw_text_shadow(draw, (rx, d_y1 + 40), '今日运势指南', card_title, COLOR_TEAL_DARK)
    _draw_text_shadow(draw, (rx, d_y1 + 96), f'● {hint_text}', card_desc, COLOR_BLUE_DARK)
    draw.text((rx, d_y1 + 144), '● 今日打卡完成，每日凌晨 00:00 重置运势', font=card_desc, fill=COLOR_TEAL_MUTED)
    draw.text(
        (rx, d_y1 + 190),
        '● 回复此图发送【提取背景】可直接获取本张高清原图',
        font=card_desc,
        fill=COLOR_HIGHLIGHT,
    )

    q_x1, q_y1, q_x2, q_y2 = 75, 705, 1125, 875
    rounded_rect(draw, (q_x1, q_y1, q_x2, q_y2), 26, (255, 255, 255, 130), (255, 255, 255, 210), 2)
    draw.text((q_x1 + 45, q_y1 + 28), '✦ 今日寄语', font=card_title, fill=COLOR_TEAL_DARK)
    draw.text((q_x1 + 45, q_y1 + 86), f'“{quote_text}”', font=quote, fill=COLOR_BLUE_DARK)

    card_w = (1050 - 3 * 16) // 4
    card_h = 125
    start_gx, start_gy = 75, 910
    for index, (star, name) in enumerate(BAND_LABELS):
        row, column = divmod(index, 4)
        bx1 = start_gx + column * (card_w + 16)
        by1 = start_gy + row * (card_h + 16)
        bx2, by2 = bx1 + card_w, by1 + card_h
        if index == active_index:
            rounded_rect(
                draw,
                (bx1 - 2, by1 - 2, bx2 + 2, by2 + 2),
                20,
                COLOR_ACTIVE_FILL,
                (255, 255, 255, 255),
                3,
            )
            draw.text((bx1 + 18, by1 + 22), star, font=grid_sub, fill=(255, 240, 245, 255))
            draw.text((bx1 + 18, by1 + 60), name, font=card_desc, fill=(255, 255, 255, 255))
        else:
            rounded_rect(draw, (bx1, by1, bx2, by2), 18, (255, 255, 255, 120), (255, 255, 255, 190), 1)
            draw.text((bx1 + 16, by1 + 22), star, font=grid_sub, fill=COLOR_BLUE_MUTED)
            draw.text((bx1 + 16, by1 + 60), name, font=card_desc, fill=COLOR_TEAL_DARK)

    f_x1, f_y1, f_x2, f_y2 = 75, 1205, 1125, 1280
    rounded_rect(draw, (f_x1, f_y1, f_x2, f_y2), 20, (255, 255, 255, 140), (255, 255, 255, 210), 1)

    id_label = '🎨 当前背景面板ID：'
    label_box = draw.textbbox((0, 0), id_label, font=footer)
    label_width = label_box[2] - label_box[0]
    draw.text((f_x1 + 30, f_y1 + 26), id_label, font=footer, fill=COLOR_TEAL_DARK)
    safe_bg_id = str(bg_id)
    if len(safe_bg_id) > 26:
        safe_bg_id = safe_bg_id[:24] + '...'
    draw.text((f_x1 + 30 + label_width + 4, f_y1 + 26), safe_bg_id, font=footer, fill=(79, 70, 229, 255))

    tip = '（回复本消息发送【提取背景】获取高清原图）'
    tip_box = draw.textbbox((0, 0), tip, font=footer)
    tip_width = tip_box[2] - tip_box[0]
    draw.text((f_x2 - tip_width - 30, f_y1 + 26), tip, font=footer, fill=COLOR_BLUE_MUTED)

    canvas = Image.alpha_composite(canvas, glass)
    return image_bytes(canvas.crop((0, 0, WIDTH, CONTENT_HEIGHT)))


@to_thread
def render_luck_card(
    bg_path: Path | None,
    avatar_img: Image.Image | None,
    username: str,
    luck: int,
    tier_name: str,
    hint_text: str,
    quote_text: str,
    active_index: int,
    bg_id: str,
) -> bytes:
    return _render_sync(bg_path, avatar_img, username, luck, tier_name, hint_text, quote_text, active_index, bg_id)
