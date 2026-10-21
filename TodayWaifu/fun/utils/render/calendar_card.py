"""🦌 / 扣 月度打卡日历图。"""

import calendar
from typing import TypedDict

from PIL import Image, ImageDraw

from gsuid_core.pool import to_thread

from ..fonts import title_font, number_font
from ..image_lib import image_bytes, rounded_rect
from ..calendar_logic import month_weeks

WIDTH = 900
HEIGHT = 1250
MARGIN = 60
GRID_TOP = 470
CELL_HEIGHT = 90
CELL_GAP = 8

COLOR_BG_TOP = (243, 249, 255)
COLOR_BG_BOTTOM = (231, 244, 240)
COLOR_INK = (32, 48, 60, 255)
COLOR_MUTED = (108, 132, 148, 255)
COLOR_TEAL = (13, 148, 136, 255)
COLOR_BLUE = (3, 105, 161, 255)
COLOR_DAY_BG = (255, 255, 255, 190)
COLOR_MARK_BG = (13, 148, 136, 225)


class CalendarSummary(TypedDict):
    """日历图头部的统计信息。"""

    name: str
    year: int
    month: int
    days: int
    total: int
    streak: int
    life_total: int
    life_days: int
    title: str
    line: str


def _background() -> Image.Image:
    image = Image.new('RGBA', (WIDTH, HEIGHT), COLOR_BG_TOP + (255,))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / (HEIGHT - 1)
        color = tuple(int(COLOR_BG_TOP[i] + (COLOR_BG_BOTTOM[i] - COLOR_BG_TOP[i]) * ratio) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color + (255,))
    return image


def _render_sync(icon: Image.Image | None, summary: CalendarSummary, marks: dict[int, int]) -> bytes:
    canvas = _background()
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    title = title_font(46)
    sub = title_font(24)
    label = title_font(22)
    value = number_font(40)
    cell_day = title_font(20)
    cell_mark = title_font(26)
    footer = title_font(22)

    header_x, header_y = MARGIN, 42
    icon_size = 0
    if icon is not None:
        icon_size = 84
        resized_icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        overlay.paste(resized_icon, (header_x, header_y), resized_icon)
    text_x = header_x + (icon_size + 22 if icon_size else 0)
    draw.text((text_x, header_y + 2), f'{summary["name"]}打卡日历', font=title, fill=COLOR_INK)
    draw.text(
        (text_x, header_y + 58),
        f'{summary["year"]} 年 {summary["month"]} 月 · {summary["title"]}',
        font=sub,
        fill=COLOR_TEAL,
    )

    card_y = 150
    rounded_rect(
        draw, (MARGIN, card_y, WIDTH - MARGIN, card_y + 270), 26, (255, 255, 255, 165), (255, 255, 255, 235), 2
    )

    stats: tuple[tuple[str, str], ...] = (
        ('本月打卡', f'{summary["days"]} 天'),
        ('本月次数', f'{summary["total"]} 次'),
        ('当前连签', f'{summary["streak"]} 天'),
        ('生涯累计', f'{summary["life_total"]} 次'),
    )
    for index, (stat_name, stat_value) in enumerate(stats):
        row, column = divmod(index, 2)
        box_x = MARGIN + 30 + column * 380
        box_y = card_y + 28 + row * 88
        draw.text((box_x, box_y), stat_name, font=label, fill=COLOR_MUTED)
        draw.text((box_x, box_y + 30), stat_value, font=value, fill=COLOR_BLUE)

    draw.text(
        (MARGIN + 30, card_y + 212),
        f'生涯打卡 {summary["life_days"]} 天 · 称号「{summary["title"]}」',
        font=label,
        fill=COLOR_MUTED,
    )

    grid_left = MARGIN
    grid_width = WIDTH - MARGIN * 2
    weeks = month_weeks(summary['year'], summary['month'])
    columns = max(len(week) for week in weeks) if weeks else 7
    cell_width = (grid_width - CELL_GAP * (columns - 1)) // columns

    week_names = ('一', '二', '三', '四', '五', '六', '日')
    for index in range(columns):
        center_x = grid_left + index * (cell_width + CELL_GAP) + cell_width // 2
        draw.text((center_x, GRID_TOP - 30), week_names[index], font=label, fill=COLOR_MUTED, anchor='mm')

    for row, week in enumerate(weeks):
        for column, day in enumerate(week):
            if day == 0:
                continue
            x1 = grid_left + column * (cell_width + CELL_GAP)
            y1 = GRID_TOP + row * (CELL_HEIGHT + CELL_GAP)
            x2, y2 = x1 + cell_width, y1 + CELL_HEIGHT
            count = marks[day] if day in marks else 0
            if count > 0:
                rounded_rect(draw, (x1, y1, x2, y2), 16, COLOR_MARK_BG, (255, 255, 255, 235), 2)
                draw.text((x1 + 12, y1 + 10), str(day), font=cell_day, fill=(255, 255, 255, 220))
                draw.text(
                    (x1 + cell_width // 2, y1 + 58),
                    f'×{count}' if count > 1 else '√',
                    font=cell_mark,
                    fill=(255, 255, 255, 255),
                    anchor='mm',
                )
            else:
                rounded_rect(draw, (x1, y1, x2, y2), 16, COLOR_DAY_BG, (255, 255, 255, 210), 1)
                draw.text((x1 + 12, y1 + 10), str(day), font=cell_day, fill=COLOR_MUTED)

    foot_y = GRID_TOP + len(weeks) * (CELL_HEIGHT + CELL_GAP) + 24
    foot_y = max(foot_y, HEIGHT - 150)
    rounded_rect(draw, (MARGIN, foot_y, WIDTH - MARGIN, foot_y + 96), 22, (255, 255, 255, 165), (255, 255, 255, 235), 2)
    draw.text((MARGIN + 26, foot_y + 18), summary['line'], font=footer, fill=COLOR_BLUE)
    month_days = calendar.monthrange(summary['year'], summary['month'])[1]
    draw.text(
        (MARGIN + 26, foot_y + 54),
        f'本月共 {month_days} 天 · 继续加油，别断了连签',
        font=label,
        fill=COLOR_MUTED,
    )

    return image_bytes(Image.alpha_composite(canvas, overlay))


@to_thread
def render_calendar_card(icon: Image.Image | None, summary: CalendarSummary, marks: dict[int, int]) -> bytes:
    return _render_sync(icon, summary, marks)
