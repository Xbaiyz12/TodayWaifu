"""从 Event 里安全地取昵称与头像（sender 是 Dict[str, Any]，这里统一收窄）。"""

from gsuid_core.models import Event

from .avatars import qq_avatar_url

_NAME_KEYS = ('card', 'nickname', 'name')


def sender_name(ev: Event) -> str:
    for key in _NAME_KEYS:
        if key not in ev.sender:
            continue
        value = ev.sender[key]
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ev.user_id


def sender_avatar(ev: Event) -> str:
    if 'avatar' in ev.sender:
        value = ev.sender['avatar']
        if isinstance(value, str) and value.strip():
            return value.strip()
    return qq_avatar_url(ev.user_id)
