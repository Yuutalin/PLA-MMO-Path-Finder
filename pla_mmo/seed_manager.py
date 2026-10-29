from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading

from pla_mmo.seed_reader import read_seed_file, validate_seed


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class SeedManager:
    def __init__(self, settings_store):
        self.settings_store = settings_store
        self._lock = threading.RLock()
        self.current_seed: str | None = None
        self.state = {
            "status": "未读取",
            "error": None,
            "file_mtime": None,
            "last_attempt_at": None,
            "last_successful_read_at": None,
            "source_path": None,
            "pending_seed": None,
        }
        self._load_on_start()

    def _load_on_start(self):
        with self._lock:
            settings = self.settings_store.load()
            if settings.get("seed_source_mode") == "manual":
                raw = settings.get("manual_seed", "")
                if raw:
                    try:
                        self.current_seed = validate_seed(raw)
                        self.state.update({
                            "status": "手动 Seed 已加载",
                            "error": None,
                            "last_successful_read_at": _now(),
                        })
                    except ValueError as exc:
                        self.state.update({"status": "读取失败", "error": str(exc)})
            elif settings.get("seed_file_path"):
                self.reload(confirm=True)

    def snapshot(self) -> dict:
        with self._lock:
            settings = self.settings_store.load()
            return {
                "ok": True,
                "current_seed": self.current_seed,
                "source_mode": settings.get("seed_source_mode", "file"),
                "source_path": (
                    settings.get("seed_file_path", "")
                    if settings.get("seed_source_mode") == "file"
                    else "手动输入"
                ),
                "file_mtime": self.state.get("file_mtime"),
                "last_attempt_at": self.state.get("last_attempt_at"),
                "last_successful_read_at": self.state.get("last_successful_read_at"),
                "status": self.state.get("status"),
                "error": self.state.get("error"),
                "pending_seed": self.state.get("pending_seed"),
            }

    def reload(self, confirm: bool = False, expected_seed: str | None = None) -> dict:
        with self._lock:
            settings = self.settings_store.load()
            if settings.get("seed_source_mode") != "file":
                return {
                    **self.snapshot(),
                    "ok": False,
                    "error": "当前 Seed 来源是手动输入。请先在设置中切换到指定 TXT 文件模式。",
                }

            file_path = settings.get("seed_file_path", "")
            self.state["last_attempt_at"] = _now()
            try:
                info = read_seed_file(file_path)
            except ValueError as exc:
                self.state.update({
                    "status": "读取失败",
                    "error": str(exc),
                    "pending_seed": None,
                })
                return {**self.snapshot(), "ok": False, "error": str(exc)}

            candidate = info["seed"]
            previous = self.current_seed
            # A file can change while the themed confirmation dialog is open.
            # Never apply a different Seed from the one the user actually saw.
            if confirm and expected_seed is not None and candidate != str(expected_seed):
                self.state.update({
                    "status": "文件中的 Seed 再次变化，等待确认",
                    "error": None,
                    "pending_seed": candidate,
                })
                return {
                    "ok": True,
                    "needs_confirmation": True,
                    "previous_seed": previous,
                    "candidate_seed": candidate,
                    "message": "确认期间 TXT 文件中的 Seed 再次变化，请重新确认。",
                    **self.snapshot(),
                }
            if previous is not None and candidate != previous and not confirm:
                self.state["status"] = "发现 Seed 变化，等待确认"
                self.state["error"] = None
                self.state["pending_seed"] = candidate
                return {
                    "ok": True,
                    "needs_confirmation": True,
                    "previous_seed": previous,
                    "candidate_seed": candidate,
                    "message": "文件中的 Seed 与当前 Seed 不同，是否切换？",
                    **self.snapshot(),
                }

            self.current_seed = candidate
            self.state.update({
                "status": "读取成功",
                "error": None,
                "file_mtime": info.get("file_mtime"),
                "last_successful_read_at": _now(),
                "source_path": info.get("path"),
                "pending_seed": None,
            })
            return {
                "ok": True,
                "changed": previous is not None and candidate != previous,
                "previous_seed": previous,
                "current_seed": candidate,
                **self.snapshot(),
            }

    def cancel_pending(self) -> dict:
        """Clear a rejected confirmation candidate without changing the active Seed."""
        with self._lock:
            self.state["pending_seed"] = None
            if "等待确认" in str(self.state.get("status") or ""):
                self.state["status"] = "已保留当前 Seed"
                self.state["error"] = None
            return self.snapshot()

    def select_file(self, file_path: str, confirm: bool = False) -> dict:
        with self._lock:
            path = str(file_path or "").strip()
            if not path:
                return {**self.snapshot(), "ok": False, "error": "没有选择文件。"}
            if Path(path).suffix.lower() != ".txt":
                return {**self.snapshot(), "ok": False, "error": "请选择 .txt 文件。"}

            try:
                self.settings_store.update({
                    "seed_source_mode": "file",
                    "seed_file_path": path,
                })
            except ValueError as exc:
                return {**self.snapshot(), "ok": False, "error": str(exc)}

            result = self.reload(confirm=confirm)
            result["selected_path"] = path
            return result

    def set_manual_seed(self, raw_seed, confirm: bool = False) -> dict:
        with self._lock:
            try:
                candidate = validate_seed(raw_seed)
            except ValueError as exc:
                return {**self.snapshot(), "ok": False, "error": str(exc)}

            previous = self.current_seed
            if previous is not None and candidate != previous and not confirm:
                self.state["status"] = "手动 Seed 变化，等待确认"
                self.state["error"] = None
                self.state["pending_seed"] = candidate
                return {
                    "ok": True,
                    "needs_confirmation": True,
                    "previous_seed": previous,
                    "candidate_seed": candidate,
                    "message": "输入的 Seed 与当前 Seed 不同，是否切换？",
                    **self.snapshot(),
                }

            try:
                self.settings_store.update({
                    "seed_source_mode": "manual",
                    "manual_seed": candidate,
                })
            except ValueError as exc:
                return {**self.snapshot(), "ok": False, "error": str(exc)}

            self.current_seed = candidate
            self.state.update({
                "status": "手动 Seed 已应用",
                "error": None,
                "file_mtime": None,
                "last_attempt_at": _now(),
                "last_successful_read_at": _now(),
                "source_path": None,
                "pending_seed": None,
            })
            return {
                "ok": True,
                "changed": previous is not None and candidate != previous,
                "previous_seed": previous,
                "current_seed": candidate,
                **self.snapshot(),
            }

