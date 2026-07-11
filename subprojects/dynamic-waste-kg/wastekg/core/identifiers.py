"""生成紧凑、稳定且适合跨进程持久化的业务 ID。"""

from __future__ import annotations

from base64 import b32encode
from hashlib import blake2b


def stable_compact_id(prefix: str, source: str) -> str:
    """用 64 位摘要生成短 ID；原始来源应另存为证据字段。"""

    normalized_prefix = prefix.strip().lower().rstrip("_")
    if not normalized_prefix:
        raise ValueError("prefix must not be empty")
    if not source:
        raise ValueError("source must not be empty")
    digest = blake2b(source.encode("utf-8"), digest_size=8).digest()
    token = b32encode(digest).decode("ascii").rstrip("=").lower()
    return f"{normalized_prefix}_{token}"
