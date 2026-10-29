"""Small local-launch helpers that do not depend on Flask.

The app chooses another loopback port when an older version is still running,
so a new launcher never silently opens the old version on port 5000.
"""
from __future__ import annotations

import os
import socket


def choose_local_port(preferred: int = 5000, attempts: int = 21, host: str = "127.0.0.1") -> int:
    """Return the first bindable local port, starting at PLA_PORT or preferred.

    Ports are probed by binding the same loopback address the Flask app uses.
    The socket is released immediately before Flask binds; this greatly reduces
    the chance of reusing a port owned by a previous app instance.
    """
    env_port = os.environ.get("PLA_PORT", "").strip()
    if env_port:
        try:
            preferred = int(env_port)
        except ValueError as exc:
            raise ValueError(f"PLA_PORT 必须是有效端口号，当前值：{env_port!r}") from exc
    if not 1 <= preferred <= 65535:
        raise ValueError(f"端口号超出范围：{preferred}")

    candidates = [preferred + offset for offset in range(max(1, attempts)) if preferred + offset <= 65535]
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(
        f"无法在 {host} 的 {preferred}–{candidates[-1] if candidates else preferred} 端口范围内找到可用端口。"
    )
