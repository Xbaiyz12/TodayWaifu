"""塔罗占卜出图：深色星幕 + 三张牌面 + 逐张牌意。"""

import math
import random
from typing import TypedDict

from PIL import Image, ImageDraw

from gsuid_core.pool import to_thread

from ..fonts import title_font
from ..image_lib import wrap_text, image_bytes, rounded_rect

WIDTH = 1200
HEIGHT = 980
CARD_WIDTH = 300
CARD_HEIGHT = 440
CARD_GAP = 40

ROMAN = (
    '0',
    'I',
    'II',
    'III',
    'IV',
    'V',
    'VI',
    'VII',
    'VIII',
    'IX',
    'X',
    'XI',
    'XII',
    'XIII',
    'XIV',
    'XV',
    'XVI',
    'XVII',
    'XVIII',
    'XIX',
    'XX',
    'XXI',
)

COLOR_TOP = (28, 24, 58)
COLOR_BOTTOM = (56, 38, 88)
COLOR_GOLD = (232, 197, 122, 255)
COLOR_TEXT = (238, 234, 250, 255)
COLOR_MUTED = (186, 178, 214, 255)


class TarotDraw(TypedDict):
    """一张牌的展示数据。"""

    name: str
    name_en: str
    arcana: str
    suit: str
    number: int
    reversed: bool
    meaning: str
    keywords: list[str]


def _background() -> Image.Image:
    image = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / (HEIGHT - 1)
        color = tuple(int(COLOR_TOP[i] + (COLOR_BOTTOM[i] - COLOR_TOP[i]) * ratio) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color + (255,))

    # 固定随机种子，保证同一张图每次生成一致
    rng = random.Random(20260101)
    for _ in range(160):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, HEIGHT - 1)
        radius = rng.choice((1, 1, 1, 2))
        alpha = rng.randint(70, 190)
        draw.ellipse((x, y, x + radius, y + radius), fill=(255, 255, 255, alpha))
    return image


def _card_number_label(card: TarotDraw) -> str:
    if card['arcana'] == 'major':
        index = card['number']
        return ROMAN[index] if 0 <= index < len(ROMAN) else str(index)
    return card['suit']


def _draw_ornament(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, radius: int) -> None:
    draw.ellipse(
        (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
        outline=COLOR_GOLD,
        width=2,
    )
    points: list[tuple[float, float]] = []
    for step in range(10):
        angle = math.pi / 2 + step * math.pi / 5
        length = radius * (0.92 if step % 2 == 0 else 0.42)
        points.append((center_x + length * math.cos(angle), center_y - length * math.sin(angle)))
    draw.polygon(points, outline=(200, 168, 240, 235))


def _draw_card(canvas: Image.Image, card: TarotDraw, x: int, y: int) -> None:
    draw = ImageDraw.Draw(canvas)
    name_font = title_font(30)
    small_font = title_font(20)
    tag_font = title_font(22)
    body_font = title_font(19)

    frame = (18, 16, 40, 235)
    border = COLOR_GOLD if not card['reversed'] else (168, 148, 210, 255)
    rounded_rect(draw, (x, y, x + CARD_WIDTH, y + CARD_HEIGHT), 22, frame, border, 3)
    rounded_rect(
        draw,
        (x + 10, y + 10, x + CARD_WIDTH - 10, y + CARD_HEIGHT - 10),
        16,
        None,
        (255, 255, 255, 45),
        1,
    )

    label = _card_number_label(card)
    draw.text((x + CARD_WIDTH // 2, y + 36), label, font=small_font, fill=COLOR_GOLD, anchor='mm')
    _draw_ornament(draw, x + CARD_WIDTH // 2, y + 190, 88)

    draw.text((x + CARD_WIDTH // 2, y + 306), card['name'], font=name_font, fill=COLOR_TEXT, anchor='mm')

    tag = '逆位' if card['reversed'] else '正位'
    tag_color = (196, 160, 232, 255) if card['reversed'] else COLOR_GOLD
    rounded_rect(
        draw,
        (x + CARD_WIDTH // 2 - 52, y + 340, x + CARD_WIDTH // 2 + 52, y + 384),
        18,
        (255, 255, 255, 26),
        tag_color,
        2,
    )
    draw.text((x + CARD_WIDTH // 2, y + 362), tag, font=tag_font, fill=tag_color, anchor='mm')

    lines = wrap_text(card['meaning'], body_font, CARD_WIDTH - 24)
    line_y = y + CARD_HEIGHT + 26
    for line in lines[:7]:
        draw.text((x + CARD_WIDTH // 2, line_y), line, font=body_font, fill=COLOR_MUTED, anchor='mm')
        line_y += 28

    keywords = ' · '.join(card['keywords'])
    draw.text((x + CARD_WIDTH // 2, line_y + 6), keywords, font=small_font, fill=COLOR_GOLD, anchor='mm')


def _render_sync(question: str, intro: str, draws: list[TarotDraw]) -> bytes:
    canvas = _background()
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    header = title_font(46)
    sub = title_font(24)
    footer = title_font(20)

    draw.text((60, 48), '塔罗占卜', font=header, fill=COLOR_TEXT)
    question_text = question if question else '（未指定问题，看看当下的能量）'
    draw.text((60, 112), f'所问：{question_text}', font=sub, fill=COLOR_GOLD)
    draw.text((60, 154), intro, font=footer, fill=COLOR_MUTED)

    total_width = len(draws) * CARD_WIDTH + (len(draws) - 1) * CARD_GAP
    start_x = (WIDTH - total_width) // 2
    for index, card in enumerate(draws):
        _draw_card(overlay, card, start_x + index * (CARD_WIDTH + CARD_GAP), 216)

    draw.text(
        (WIDTH // 2, HEIGHT - 42),
        '牌意仅供娱乐参考 · 真正的答案还在你自己手里',
        font=footer,
        fill=COLOR_MUTED,
        anchor='mm',
    )
    return image_bytes(Image.alpha_composite(canvas, overlay))


@to_thread
def render_tarot_card(question: str, intro: str, draws: list[TarotDraw]) -> bytes:
    return _render_sync(question, intro, draws)
