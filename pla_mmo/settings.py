from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from pla_mmo.paths import get_data_dir, get_project_root

PROJECT_ROOT = get_project_root()
VALID_THEMES = {"forest", "ocean", "snow", "lavender", "amber"}
VALID_MODES = {"light", "dark"}
VALID_RESEARCH_LEVELS = {"base", "level10", "perfect"}
VALID_SEED_SOURCES = {"file", "manual"}


def default_seed_path() -> str:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return ""
    return str(
        Path(appdata)
        / "pokeldn"
        / "plugin-data"
        / "junli-pla-mmo-seed"
        / "latest_seed.txt"
    )


DEFAULT_SETTINGS = {
    "seed_source_mode": "file",
    "seed_file_path": default_seed_path(),
    "manual_seed": "",
    "default_research_level": "level10",
    "default_shiny_charm": True,
    "pokemon_research_levels": {},
    "appearance_theme": "forest",
    "appearance_mode": "light",
    "appearance_preferences_saved": False,
}


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return default


class SettingsStore:
    """Thread-safe, atomic settings storage with a last-known-good backup."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path = self.path.with_name(f"{self.path.stem}.backup{self.path.suffix}")
        self._lock = threading.RLock()
        self._last_warning: str | None = None
        self._last_read_problem: str | None = None
        self._recovered_from_backup = False

    def _read_dict(self, path: Path) -> dict | None:
        self._last_read_problem = None
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as exc:
            self._last_read_problem = "malformed"
            self._last_warning = f"配置文件 {path.name} 不是有效 JSON：{exc}"
            return None
        except OSError as exc:
            self._last_read_problem = "unreadable"
            self._last_warning = f"无法读取配置文件 {path.name}：{exc}"
            return None
        if not isinstance(loaded, dict):
            self._last_read_problem = "malformed"
            self._last_warning = f"配置文件 {path.name} 的顶层结构不是对象。"
            return None
        return loaded

    def _preserve_invalid_file(self) -> Path | None:
        if not self.path.is_file():
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        preserved = self.path.with_name(f"{self.path.stem}.corrupt-{stamp}{self.path.suffix}")
        try:
            self.path.replace(preserved)
            return preserved
        except OSError:
            return None

    def _normalize(self, loaded: dict | None) -> dict:
        settings = dict(DEFAULT_SETTINGS)
        settings["pokemon_research_levels"] = {}
        if loaded:
            settings.update(loaded)
            if "appearance_preferences_saved" not in loaded:
                # Older releases stored appearance only in WebView localStorage.
                # Let the frontend migrate that preference once into settings.json.
                settings["appearance_preferences_saved"] = (
                    "appearance_theme" in loaded or "appearance_mode" in loaded
                )

        if settings.get("seed_source_mode") not in VALID_SEED_SOURCES:
            settings["seed_source_mode"] = "file"
        for key in ("seed_file_path", "manual_seed"):
            value = settings.get(key, "")
            settings[key] = value.strip() if isinstance(value, str) else ""
        if settings.get("default_research_level") not in VALID_RESEARCH_LEVELS:
            settings["default_research_level"] = "level10"
        settings["default_shiny_charm"] = _as_bool(settings.get("default_shiny_charm"), True)
        raw_species_levels = settings.get("pokemon_research_levels", {})
        normalized_species_levels = {}
        if isinstance(raw_species_levels, dict):
            for raw_species, raw_level in list(raw_species_levels.items())[:500]:
                species = str(raw_species or "").strip()
                level = str(raw_level or "").strip()
                if species and len(species) <= 100 and level in VALID_RESEARCH_LEVELS:
                    normalized_species_levels[species] = level
        settings["pokemon_research_levels"] = normalized_species_levels
        if settings.get("appearance_theme") not in VALID_THEMES:
            settings["appearance_theme"] = "forest"
        if settings.get("appearance_mode") not in VALID_MODES:
            settings["appearance_mode"] = "light"
        settings["appearance_preferences_saved"] = _as_bool(
            settings.get("appearance_preferences_saved"), False
        )
        # Remove obsolete remote-engine options from older versions.
        settings.pop("remote_api_base", None)
        settings.pop("request_timeout_seconds", None)
        return settings

    def load(self) -> dict:
        with self._lock:
            loaded = self._read_dict(self.path)
            primary_problem = self._last_read_problem
            if loaded is None:
                # Preserve malformed JSON for diagnosis, but never rename a file
                # that merely failed because of permissions or another I/O error.
                if primary_problem == "malformed":
                    self._preserve_invalid_file()
                backup = self._read_dict(self.backup_path)
                if backup is not None:
                    loaded = backup
                    self._recovered_from_backup = True
                    self._last_warning = "主配置不可用，已从上次有效配置备份恢复。"
            return self._normalize(loaded)

    def _backup_current_file(self) -> None:
        if not self.path.is_file():
            return
        # Do not replace a good backup with an unreadable or non-object file.
        current = self._read_dict(self.path)
        if current is None:
            return
        temp = self.backup_path.with_name(
            f".{self.backup_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            shutil.copy2(self.path, temp)
            os.replace(temp, self.backup_path)
        except OSError as exc:
            # A backup is a safety net, not a reason to block ordinary settings
            # saves when a restrictive filesystem prevents creating the copy.
            self._last_warning = f"无法更新配置备份：{exc}"
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def _write_atomic(self, settings: dict) -> None:
        temp = self.path.with_name(f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(settings, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def update(self, updates: dict) -> dict:
        if not isinstance(updates, dict):
            raise ValueError("设置内容格式无效。")
        with self._lock:
            current = self.load()
            allowed = {
                "seed_source_mode",
                "seed_file_path",
                "manual_seed",
                "default_research_level",
                "default_shiny_charm",
                "pokemon_research_levels",
                "appearance_theme",
                "appearance_mode",
            }
            for key in allowed:
                if key in updates:
                    current[key] = updates[key]

            mode = str(current.get("seed_source_mode", "file"))
            if mode not in VALID_SEED_SOURCES:
                raise ValueError("Seed 来源模式只能是指定 TXT 文件或手动输入。")
            current["seed_source_mode"] = mode

            current["seed_file_path"] = str(current.get("seed_file_path") or "").strip()
            current["manual_seed"] = str(current.get("manual_seed") or "").strip()
            default_level = str(current.get("default_research_level", "level10"))
            if default_level not in VALID_RESEARCH_LEVELS:
                raise ValueError("默认研究等级只能是基础、研究等级 10 或完美研究。")
            current["default_research_level"] = default_level
            current["default_shiny_charm"] = _as_bool(current.get("default_shiny_charm"), True)
            if "pokemon_research_levels" in updates:
                raw_species_levels = updates["pokemon_research_levels"]
                if not isinstance(raw_species_levels, dict):
                    raise ValueError("宝可梦研究等级配置格式无效。")
                if len(raw_species_levels) > 500:
                    raise ValueError("宝可梦研究等级配置数量超出限制。")
                normalized_species_levels = {}
                for raw_species, raw_level in raw_species_levels.items():
                    species = str(raw_species or "").strip()
                    level = str(raw_level or "").strip()
                    if not species or len(species) > 100:
                        raise ValueError("宝可梦研究等级配置包含无效名称。")
                    if level not in VALID_RESEARCH_LEVELS:
                        raise ValueError(f"宝可梦「{species}」的研究等级无效。")
                    normalized_species_levels[species] = level
                current["pokemon_research_levels"] = normalized_species_levels

            appearance_theme = str(current.get("appearance_theme", "forest"))
            if appearance_theme not in VALID_THEMES:
                raise ValueError("界面主题无效。")
            current["appearance_theme"] = appearance_theme
            appearance_mode = str(current.get("appearance_mode", "light"))
            if appearance_mode not in VALID_MODES:
                raise ValueError("外观模式只能是日间或夜间。")
            current["appearance_mode"] = appearance_mode
            if "appearance_theme" in updates or "appearance_mode" in updates:
                current["appearance_preferences_saved"] = True

            self._backup_current_file()
            self._write_atomic(current)
            return current

    def public_view(self) -> dict:
        settings = self.load()
        return {
            "seed_source_mode": settings["seed_source_mode"],
            "seed_file_path": settings["seed_file_path"],
            "manual_seed": settings["manual_seed"],
            "default_research_level": settings.get("default_research_level", "level10"),
            "default_shiny_charm": settings.get("default_shiny_charm", True),
            "pokemon_research_levels": dict(settings.get("pokemon_research_levels", {})),
            "appearance_theme": settings.get("appearance_theme", "forest"),
            "appearance_mode": settings.get("appearance_mode", "light"),
            "appearance_preferences_saved": settings.get("appearance_preferences_saved", False),
        }

    def diagnostics(self) -> dict:
        with self._lock:
            return {
                "settings_path": str(self.path),
                "settings_exists": self.path.is_file(),
                "backup_path": str(self.backup_path),
                "backup_exists": self.backup_path.is_file(),
                "recovered_from_backup": self._recovered_from_backup,
                "warning": self._last_warning,
            }
