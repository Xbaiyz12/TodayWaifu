"""本地图库扫描与图片基础操作（PIL 原语）。"""

import io
import random
import asyncio
import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from gsuid_core.pool import to_thread
from gsuid_core.logger import logger

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}


def _is_landscape(path: Path) -> bool:
    # 只读文件头拿尺寸，不整图解码；坏图直接判为非横图
    try:
        with Image.open(path) as image:
            return image.width > image.height
    except OSError:
        return False


@to_thread
def _scan_dir(root: Path, landscape_only: bool) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        if landscape_only and not _is_landscape(path):
            continue
        found.append(path)
    return found


class ImageLibrary:
    """目录图库：惰性扫描 + TTL 缓存，支持随机取图与关键词查图。"""

    def __init__(self, root: Path, landscape_only: bool = False, ttl: int = 600) -> None:
        self._root = root
        self._landscape_only = landscape_only
        self._ttl = ttl
        self._files: list[Path] = []
        self._index: dict[str, Path] = {}
        self._scanned_at = 0.0
        # 并发突发时避免同一份目录被重复扫描（1714 张图全扫一次不便宜）
        self._lock = asyncio.Lock()

    @property
    def root(self) -> Path:
        return self._root

    def set_root(self, root: Path) -> None:
        """切换图库目录（配置项改动或目录不存在时重新指向）。"""
        if root == self._root:
            return
        self._root = root
        self._files = []
        self._index = {}
        self._scanned_at = 0.0

    def _build_index(self, files: list[Path]) -> dict[str, Path]:
        index: dict[str, Path] = {}
        for path in files:
            stem = path.stem
            index.setdefault(stem.lower(), path)
            parts = stem.split('_')
            if len(parts) > 1:
                if parts[-1].isdigit():
                    index.setdefault(parts[-1], path)
                index.setdefault(parts[0].lower(), path)
        return index

    async def _ensure(self) -> None:
        now = datetime.datetime.now().timestamp()
        if self._files and now - self._scanned_at < self._ttl:
            return
        async with self._lock:
            # 等锁期间别人可能已经扫完，二次确认
            now = datetime.datetime.now().timestamp()
            if self._files and now - self._scanned_at < self._ttl:
                return
            files = await _scan_dir(self._root, self._landscape_only)
            self._files = files
            self._index = self._build_index(files)
            self._scanned_at = now
        if not self._files:
            logger.debug(f'[今日老婆·图库] {self._root} 下没有可用图片')

    async def all(self) -> list[Path]:
        await self._ensure()
        return self._files

    async def random(self) -> Path | None:
        await self._ensure()
        if not self._files:
            return None
        return random.choice(self._files)

    async def find(self, query: str) -> Path | None:
        await self._ensure()
        key = query.strip().lower()
        if not key:
            return None
        if key in self._index:
            return self._index[key]
        for path in self._files:
            if key in path.stem.lower():
                return path
        return None


def open_image(path: Path) -> Image.Image | None:
    """打开图片并转 RGBA；文件损坏时返回 None 而不是让渲染整条链路炸掉。"""
    try:
        with Image.open(path) as image:
            return image.convert('RGBA')
    except OSError as e:
        logger.debug(f'[今日老婆·图库] 无法打开 {path}: {e}')
        return None


def cover_crop(image: Image.Image, width: int, height: int) -> Image.Image:
    """等比放大后居中裁切到目标尺寸，保证不满不空。"""
    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def circle_image(image: Image.Image, size: int) -> Image.Image:
    scaled = cover_crop(image, size, size)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    circle = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    circle.paste(scaled, (0, 0), mask)
    return circle


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, ...] | None = None,
    outline: tuple[int, ...] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def gradient_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    start_color: tuple[int, int, int],
    end_color: tuple[int, int, int],
) -> Image.Image:
    """水平渐变色文字（原打卡模板的幸运值大字效果）。"""
    probe = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    width = max(1, int(bbox[2] - bbox[0]) + 16)
    height = max(1, int(bbox[3] - bbox[1]) + 16)

    gradient = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    pixels = gradient.load()
    if pixels is not None:
        for x in range(width):
            ratio = x / max(1, width - 1)
            color = (
                int(start_color[0] + (end_color[0] - start_color[0]) * ratio),
                int(start_color[1] + (end_color[1] - start_color[1]) * ratio),
                int(start_color[2] + (end_color[2] - start_color[2]) * ratio),
                255,
            )
            for y in range(height):
                pixels[x, y] = color

    mask = Image.new('L', (width, height), 0)
    ImageDraw.Draw(mask).text((-bbox[0] + 8, -bbox[1] + 8), text, font=font, fill=255)

    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    result.paste(gradient, (0, 0), mask)
    return result


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """按像素宽度折行（中文没有词边界，逐字累计即可）。"""
    lines: list[str] = []
    current = ''
    for char in text:
        candidate = current + char
        if current and font.getlength(candidate) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def image_bytes(image: Image.Image, fmt: str = 'PNG') -> bytes:
    buffer = io.BytesIO()
    if fmt.upper() == 'JPEG':
        image.convert('RGB').save(buffer, format='JPEG', quality=88, optimize=True)
    else:
        image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()
