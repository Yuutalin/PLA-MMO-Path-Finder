from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime


MAX_SEED_TEXT_LENGTH = 128


def validate_seed(raw) -> str:
    if raw is None:
        raise ValueError("Seed 不能为空。")
    value = str(raw).strip()
    if not value:
        raise ValueError("Seed 不能为空。")
    if len(value) > MAX_SEED_TEXT_LENGTH:
        raise ValueError(f"Seed 文本过长（最多 {MAX_SEED_TEXT_LENGTH} 位）。")
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("Seed 必须是纯十进制非负整数，不接受十六进制、负号或其他文字。")
    return value


def read_seed_file(file_path: str) -> dict:
    path_text = str(file_path or "").strip()
    if not path_text:
        raise ValueError("尚未设置 Seed TXT 文件路径。")

    path = Path(path_text).expanduser()
    if not path.exists():
        raise ValueError(f"Seed 文件不存在：{path}")
    if not path.is_file():
        raise ValueError(f"指定路径不是文件：{path}")

    try:
        raw_bytes = path.read_bytes()
    except PermissionError:
        raise ValueError("没有权限读取该 Seed 文件。")
    except OSError as exc:
        raise ValueError(f"读取 Seed 文件失败：{exc}")

    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("TXT 文件不是有效的 UTF-8 文本。")

    seed = validate_seed(content)
    try:
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
    except OSError:
        mtime = None

    return {
        "seed": seed,
        "path": str(path.resolve()),
        "file_mtime": mtime,
        "size_bytes": len(raw_bytes),
    }
