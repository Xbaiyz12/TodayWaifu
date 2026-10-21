"""打卡排行榜 / 非酋榜卡片，沿用原 luck-plugin rank.html 的视觉规范。"""

from typing import TypedDict
from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.pool import to_thread

from ..fonts import title_font, number_font
from ..image_lib import cover_crop, open_image, image_bytes, circle_image, rounded_rect, gradient_text

WIDTH = 1200
ROW_HEIGHT = 100
MAX_ROWS = 15

GRADIENT_START = (255, 0, 106)
GRADIENT_END = (106, 92, 255)


class SelfInfo(TypedDict):
    """当前用户的个人卡片数据。"""

    user_name: str
    score_label: str
    rank_label: str


class RankRow(TypedDict):
    """一行榜单数据（头像单独按同序传入）。"""

    rank: int
    user_name: str
    score: int


def _render_sync(
    bg_path: Path | None,
    title: str,
    self_info: SelfInfo,
    rows: list[RankRow],
    self_avatar: Image.Image | None,
    row_avatars: list[Image.Image | None],
) -> bytes:
    top_rows = rows[:MAX_ROWS]
    board_height = max(200, len(top_rows) * ROW_HEIGHT + 50)
    height = 580 + board_height + 80

    canvas = Image.new('RGBA', (WIDTH, height), (240, 240, 245, 255))
    if bg_path is not None:
        background = open_image(bg_path)
        if background is not None:
            canvas.paste(cover_crop(background, WIDTH, height), (0, 0))

    tint = Image.new('RGBA', (WIDTH, height), (0, 0, 0, 0))
    tint_draw = ImageDraw.Draw(tint)
    for y in range(height):
        alpha = int(45 + 30 * (y / height))
        tint_draw.line([(0, y), (WIDTH, y)], fill=(15, 20, 30, alpha))
    canvas = Image.alpha_composite(canvas, tint)

    title_font_obj = title_font(50)
    p_text = title_font(34)
    desc = title_font(24)
    rank_tag = title_font(32)
    user_name = title_font(32)
    score_font = number_font(56)

    glass = Image.new('RGBA', (WIDTH, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glass)

    t_box = draw.textbbox((0, 0), title, font=title_font_obj)
    t_width = t_box[2] - t_box[0]
    draw.text((WIDTH // 2 - t_width // 2 + 2, 62), title, font=title_font_obj, fill=(0, 0, 0, 160))
    draw.text((WIDTH // 2 - t_width // 2, 60), title, font=title_font_obj, fill=(255, 255, 255, 255))

    c_x1, c_y1, c_x2 = 75, 140, 1125
    rounded_rect(draw, (c_x1, c_y1, c_x2, 360), 40, (255, 255, 255, 105), (255, 255, 255, 180), 2)

    avatar_size = 150
    p_ax, p_ay = c_x1 + 40, c_y1 + 35
    if self_avatar is not None:
        circle = circle_image(self_avatar, avatar_size)
        draw.ellipse(
            (p_ax - 3, p_ay - 3, p_ax + avatar_size + 3, p_ay + avatar_size + 3),
            fill=(255, 255, 255, 220),
        )
        glass.paste(circle, (p_ax, p_ay), circle)
    else:
        draw.ellipse(
            (p_ax, p_ay, p_ax + avatar_size, p_ay + avatar_size),
            fill=(220, 225, 235, 180),
            outline=(255, 255, 255, 220),
            width=3,
        )

    tx = c_x1 + 225
    draw.text((tx, c_y1 + 35), f'✨ 你的名稱 : {self_info["user_name"]}', font=p_text, fill=(35, 35, 40, 255))
    draw.text((tx, c_y1 + 88), f'✨ 你的数值 : {self_info["score_label"]}', font=p_text, fill=(45, 45, 50, 255))
    draw.text((tx, c_y1 + 140), f'✨ 你的排名 : {self_info["rank_label"]}', font=p_text, fill=(45, 45, 50, 255))

    d_x1, d_y1, d_x2, d_y2 = 75, 385, 1125, 495
    rounded_rect(draw, (d_x1, d_y1, d_x2, d_y2), 30, (255, 255, 255, 100), (255, 255, 255, 170), 2)
    draw.text((d_x1 + 35, d_y1 + 20), '排行说明', font=p_text, fill=(30, 30, 35, 255))
    draw.text(
        (d_x1 + 35, d_y1 + 65),
        '● 榜单按当日/当月统计 | 最多展示 15 名 | 回复图片发送【提取背景】可获取打卡原图',
        font=desc,
        fill=(60, 60, 65, 255),
    )

    l_x1, l_y1, l_x2 = 75, 520, 1125
    rounded_rect(
        draw,
        (l_x1, l_y1, l_x2, l_y1 + board_height),
        30,
        (255, 255, 255, 100),
        (255, 255, 255, 170),
        2,
    )

    list_avatar_size = 70
    for index, item in enumerate(top_rows):
        item_y = l_y1 + 25 + index * ROW_HEIGHT
        if index > 0:
            draw.line([(l_x1 + 25, item_y - 8), (l_x2 - 25, item_y - 8)], fill=(255, 255, 255, 90), width=1)

        draw.text((l_x1 + 35, item_y + 18), f'第{item["rank"]}名', font=rank_tag, fill=(35, 35, 40, 255))

        item_ax, item_ay = l_x1 + 175, item_y + 8
        avatar = row_avatars[index] if index < len(row_avatars) else None
        if avatar is not None:
            circle = circle_image(avatar, list_avatar_size)
            draw.ellipse(
                (item_ax - 2, item_ay - 2, item_ax + list_avatar_size + 2, item_ay + list_avatar_size + 2),
                fill=(255, 255, 255, 200),
            )
            glass.paste(circle, (item_ax, item_ay), circle)
        else:
            draw.ellipse(
                (item_ax, item_ay, item_ax + list_avatar_size, item_ay + list_avatar_size),
                fill=(220, 225, 235, 180),
            )

        name = item['user_name']
        if len(name) > 16:
            name = name[:15] + '...'
        draw.text((l_x1 + 270, item_y + 18), name, font=user_name, fill=(35, 35, 40, 255))

        gradient = gradient_text(str(item['score']), score_font, GRADIENT_START, GRADIENT_END)
        glass.paste(gradient, (l_x2 - gradient.width - 45, item_y + 5), gradient)

    canvas = Image.alpha_composite(canvas, glass)
    return image_bytes(canvas)


@to_thread
def render_rank_card(
    bg_path: Path | None,
    title: str,
    self_info: SelfInfo,
    rows: list[RankRow],
    self_avatar: Image.Image | None,
    row_avatars: list[Image.Image | None],
) -> bytes:
    return _render_sync(bg_path, title, self_info, rows, self_avatar, row_avatars)
