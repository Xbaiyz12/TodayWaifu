"""GIF 工具：动图加速、减速与逐帧分解（需要把图和指令发在同一条消息里）。"""

import io

from PIL import Image, ImageSequence

from gsuid_core.bot import Bot
from gsuid_core.pool import to_thread
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.ai_core.trigger_bridge import ai_return
from gsuid_core.utils.image.image_tools import change_ev_image_to_bytes

from .shared import reply, gif_sv, allowed
from .xf_config import get_int, get_bool, get_float

MAX_CANVAS_HEIGHT = 15000

SPEED_DOC = """把用户发来的 GIF 动图加速或减速后发回。
当用户说"帮我把这个动图加速""gif 慢放""动图调速度"时调用，需要同一条消息里带图片。

Args:
    text: 倍速数字，留空按 2.0 处理。例如 "2"、"0.5"、"1.5"（0.1~5.0）
"""

SPLIT_DOC = """把用户发来的 GIF 动图逐帧拆开，拼成一张竖长图发回。
当用户说"把动图分解""gif 拆帧""看看这个动图每一帧"时调用，需要同一条消息里带图片。

Args:
    text: 无需参数，留空即可
"""


class GifToolError(Exception):
    """图片本身有问题或参数不可用时，可预期、可直接回给用户的错误。"""


async def _event_image(ev: Event) -> bytes | None:
    """取当前消息里的第一张图；图片与指令必须同一条消息。"""
    if not ev.image_list:
        return None
    data = await change_ev_image_to_bytes(ev.image_list[0])
    return data if isinstance(data, bytes) else None


def _check_size(content: bytes) -> None:
    limit = get_int('xf_gif_max_mb') * 1024 * 1024
    if limit > 0 and len(content) > limit:
        raise GifToolError(f'图片体积过大（{len(content) // (1024 * 1024)}MB），上限 {get_int("xf_gif_max_mb")}MB')


def _load_frames(content: bytes, max_frames: int) -> tuple[list[Image.Image], list[int]]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            frames: list[Image.Image] = []
            durations: list[int] = []
            for frame in ImageSequence.Iterator(image):
                frames.append(frame.convert('RGBA'))
                duration = frame.info['duration'] if 'duration' in frame.info else 100
                durations.append(duration if isinstance(duration, int) and duration > 0 else 100)
                if len(frames) >= max_frames:
                    break
    except OSError as e:
        raise GifToolError('请确认这是一张有效的 GIF 动图') from e

    if not frames:
        raise GifToolError('未能从动图中读取到有效帧')
    return frames, durations


@to_thread
def _process_speed(content: bytes, speed: float, max_frames: int) -> bytes:
    frames, durations = _load_frames(content, max_frames)
    avg_duration = sum(durations) / len(durations)

    if speed >= 2.0:
        # 高倍速下抽帧，避免帧率过高被播放器丢帧
        step = max(1, int(speed))
        selected = frames[::step]
        frame_duration = int(max(20, (avg_duration * step) / speed))
    elif speed > 1.0:
        selected = frames
        frame_duration = int(max(20, avg_duration / speed))
    else:
        selected = frames
        frame_duration = int(min(1000, avg_duration / speed))

    buffer = io.BytesIO()
    selected[0].save(
        buffer,
        format='GIF',
        save_all=True,
        append_images=selected[1:],
        duration=frame_duration,
        loop=0,
        disposal=2,
    )
    return buffer.getvalue()


@to_thread
def _process_split(content: bytes, max_frames: int) -> bytes:
    frames, _ = _load_frames(content, max_frames)
    max_width = max(frame.width for frame in frames)
    total_height = sum(frame.height for frame in frames)

    scale = 1.0
    if total_height > MAX_CANVAS_HEIGHT:
        scale = MAX_CANVAS_HEIGHT / total_height

    canvas_width = int(max_width * scale)
    canvas_height = int(total_height * scale)
    canvas = Image.new('RGBA', (max(1, canvas_width), max(1, canvas_height)), (255, 255, 255, 0))

    current_y = 0
    for frame in frames:
        if scale != 1.0:
            frame = frame.resize((int(frame.width * scale), int(frame.height * scale)), Image.Resampling.LANCZOS)
        canvas.paste(frame, (0, current_y))
        current_y += frame.height

    buffer = io.BytesIO()
    canvas.save(buffer, format='PNG')
    return buffer.getvalue()


def _parse_speed(raw: str, default: float) -> float:
    text = raw.strip()
    if not text:
        return default
    # 只接受纯数字/小数，避免 float() 在奇怪输入上抛未捕获异常
    if not text.replace('.', '', 1).isdigit():
        raise GifToolError('请输入有效的数字倍率，例如：加速 2.5')
    return float(text)


async def _run_speed(bot: Bot, ev: Event, default: float) -> None:
    content = await _event_image(ev)
    if content is None:
        return await reply(bot, '请把一张 GIF 动图和指令发在同一条消息里，例如：加速 2')

    try:
        speed = _parse_speed(ev.text, default)
    except GifToolError as e:
        return await reply(bot, str(e))

    low, high = get_float('xf_gif_min_speed'), get_float('xf_gif_max_speed')
    if speed < low or speed > high:
        return await reply(bot, f'倍速需要在 {low} 到 {high} 之间哦！')

    try:
        _check_size(content)
        result = await _process_speed(content, speed, get_int('xf_gif_max_frames'))
    except GifToolError as e:
        return await reply(bot, f'处理失败：{e}')

    await bot.send(MessageSegment.image(result))
    ai_return(f'已按 {speed} 倍速处理动图并发回（输出 {len(result) // 1024} KB）。')


@gif_sv.on_command(
    ('加速', 'gif加速', '动图加速'),
    to_ai=SPEED_DOC,
    covers=['gif加速', '动图加速', '动图调速'],
    aliases=['今日老婆·GIF加速'],
)
async def gif_speed_up(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_gif_enable') or not get_bool('xf_gif_speed_enable'):
        return
    await _run_speed(bot, ev, 2.0)


@gif_sv.on_command(
    ('减速', 'gif减速', '动图减速'),
    to_ai=SPEED_DOC,
    covers=['gif减速', '动图减速', '动图慢放', 'gif慢放'],
    aliases=['今日老婆·GIF减速'],
)
async def gif_speed_down(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_gif_enable') or not get_bool('xf_gif_speed_enable'):
        return
    await _run_speed(bot, ev, 0.5)


@gif_sv.on_command(
    ('分解', 'gif分解', '动图分解'),
    to_ai=SPLIT_DOC,
    covers=['gif分解', '动图拆帧', '动图逐帧'],
    aliases=['今日老婆·GIF分解'],
)
async def gif_split(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_gif_enable') or not get_bool('xf_gif_split_enable'):
        return

    content = await _event_image(ev)
    if content is None:
        return await reply(bot, '请把一张 GIF 动图和指令发在同一条消息里，例如：分解')

    try:
        _check_size(content)
        result = await _process_split(content, get_int('xf_gif_max_frames'))
    except GifToolError as e:
        return await reply(bot, f'分解失败：{e}')

    await bot.send(MessageSegment.image(result))
    ai_return(f'已把动图逐帧拼成长图并发回（输出 {len(result) // 1024} KB）。')


@gif_sv.on_command(
    'gif帮助',
    to_ai="""查看 GIF 工具的用法说明。
当用户问"gif 怎么用""动图工具怎么玩"时调用。

Args:
    text: 无需参数，留空即可
""",
    covers=['gif帮助', '动图工具用法'],
    aliases=['今日老婆·GIF帮助'],
)
async def gif_help(bot: Bot, ev: Event) -> None:
    if not await allowed(ev) or not get_bool('xf_gif_enable'):
        return
    await bot.send(
        '🎞️ GIF 动图工具：\n'
        '1. 加速：把动图和【加速 [倍数]】发在同一条消息里（例如：加速 2）\n'
        '2. 减速：【减速 0.5】可以慢放，支持 0.1 ~ 5.0 倍速\n'
        '3. 分解：【分解】把动图逐帧拼成一张竖长图\n'
        '💡 图片要和指令放在同一条消息里哦。'
    )
