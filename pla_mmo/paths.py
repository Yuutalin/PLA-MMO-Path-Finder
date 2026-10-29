"""Resolve immutable application resources separately from writable user data."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Return the directory containing bundled resources or the source project.

    PyInstaller's one-folder builds may place support files in ``_internal`` or
    beside the executable depending on its contents-directory setting. Probe
    both locations by checking for the resources this application requires.
    """
    if getattr(sys, "frozen", False):
        candidates: list[Path] = []
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.append(Path(bundle_dir).resolve())
        if getattr(sys, "executable", None):
            candidates.append(Path(sys.executable).resolve().parent)
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate).casefold()
            if key in seen:
                continue
            seen.add(key)
            if (candidate / "templates").is_dir() and (candidate / "offline_engine").is_dir():
                return candidate
        if candidates:
            return candidates[0]
    return Path(__file__).resolve().parents[1]


def get_data_dir() -> Path:
    """Return a writable per-user directory for settings, logs and image cache."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "PLA-MMO-Path-Finder"
    if getattr(sys, "frozen", False):
        return Path.home() / ".pla-mmo-path-finder"
    return get_project_root() / "data"


def get_log_dir() -> Path:
    path = get_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
