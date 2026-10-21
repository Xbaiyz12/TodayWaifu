"""头像下载与本地缓存：缓存命中优先，失败返回 None 由渲染层画占位。"""

import io
import asyncio
import hashlib
from pathlib import Path

import httpx
from PIL import Image

from gsuid_core.pool import to_thread
from gsuid_core.logger import logger

from .paths import AVATAR_CACHE_PATH

QQ_AVATAR_URL = 'https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640'


def qq_avatar_url(user_id: str) -> str:
    return QQ_AVATAR_URL.format(user_id=user_id)


def avatar_cache_file(url: str) -> Path:
    key = hashlib.md5(url.encode('utf-8')).hexdigest()
    return AVATAR_CACHE_PATH / f'{key}.png'


@to_thread
def _load_cached(path: Path) -> Image.Image | None:
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        with Image.open(path) as image:
            return image.convert('RGBA')
    except OSError:
        return None


@to_thread
def _decode(content: bytes) -> Image.Image | None:
    try:
        with Image.open(io.BytesIO(content)) as image:
            return image.convert('RGBA')
    except OSError:
        return None


async def fetch_avatar(url: str) -> Image.Image | None:
    if not url:
        return None

    cache_file = avatar_cache_file(url)
    cached = await _load_cached(cache_file)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url)
    except httpx.HTTPError as e:
        logger.debug(f'[今日老婆·头像] 下载失败 {url}: {e}')
        return None

    if response.status_code != 200 or not response.content:
        return None

    image = await _decode(response.content)
    if image is None:
        return None
    # 缓存写失败不影响本次出图，只记 debug
    try:
        cache_file.write_bytes(response.content)
    except OSError as e:
        logger.debug(f'[今日老婆·头像] 缓存写入失败 {cache_file}: {e}')
    return image


async def fetch_avatars(urls: list[str]) -> list[Image.Image | None]:
    if not urls:
        return []
    return list(await asyncio.gather(*(fetch_avatar(url) for url in urls)))
