from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from pla_mmo.paths import get_project_root

PROJECT_ROOT = get_project_root()
POKEDEX_PATH = PROJECT_ROOT / "offline_engine" / "static" / "resources" / "pokedex.json"
HISUIDEX_PATH = PROJECT_ROOT / "offline_engine" / "static" / "resources" / "hisuidex.txt"
SPRITE_NAME_RE = re.compile(r"^c_\d+(?:-\d+)?f?s?\.png$", re.IGNORECASE)


def _slug(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


class PokemonAssetManager:
    """Optional local sprite cache. Calculation never depends on this manager."""

    def __init__(self, project_root: Path, data_dir: Path):
        self.project_root = Path(project_root)
        self.static_root = self.project_root / "static"
        # Writable image files belong in the per-user data directory, not beside
        # bundled application resources (which may be under Program Files).
        self.asset_root = Path(data_dir) / "pokemon"
        self.cache_dir = self.asset_root / "cache"
        self.custom_dir = self.asset_root / "custom"
        # Continue to read legacy images from source-tree folders after upgrade.
        self.legacy_asset_root = self.static_root / "pokemon"
        self.legacy_cache_dir = self.legacy_asset_root / "cache"
        self.legacy_custom_dir = self.legacy_asset_root / "custom"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = Path(data_dir) / "pokemon-assets-state.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._form_url_cache: dict[str, dict[str, list[str]]] = {}
        self._entries = self._load_manifest_entries()
        self._state = self._load_state()
        # "download" records consent for the current run, not a permanent
        # auto-download preference. If files are still missing on a new app
        # launch, ask again instead of silently resuming a possibly interrupted
        # network transfer.
        if self._state.get("choice") == "download" and self._entries and self._missing_files():
            self._state["choice"] = None
            self._save_state()
        self._progress: dict[str, Any] = {
            "status": "idle", "total": 0, "completed": 0, "downloaded": 0,
            "failed": 0, "current": "", "errors": [], "percent": 0,
        }
        self._worker: threading.Thread | None = None

    def _load_manifest_entries(self) -> dict[str, dict[str, Any]]:
        try:
            pokedex = json.loads(POKEDEX_PATH.read_text(encoding="utf-8"))
            entries = {str(item.get("id")): item for item in pokedex if isinstance(item, dict)}
            hisui_lines = HISUIDEX_PATH.read_text(encoding="utf-8").splitlines()
        except (OSError, json.JSONDecodeError):
            return {}

        hisui_ids: set[str] = set()
        hisui_species: set[str] = set()
        for line in hisui_lines:
            parts = [part.strip() for part in line.split("\t")]
            if len(parts) != 2 or not parts[1]:
                continue
            hisui_ids.add(parts[1])
            entry = entries.get(parts[1])
            if entry and entry.get("species"):
                hisui_species.add(str(entry["species"]))

        # Include every internal form of a species present in the Hisui dex.
        # Some visual forms (notably female Basculegion) have their own Pokédex
        # IDs but are not separate lines in hisuidex.txt.
        relevant_entries = [
            entry for entry in entries.values()
            if str(entry.get("id") or "") in hisui_ids
            or str(entry.get("species") or "") in hisui_species
        ]
        manifest: dict[str, dict[str, Any]] = {}
        for entry in relevant_entries:
            national = int(entry.get("dex_national") or 0)
            if national <= 0:
                continue
            form_id = str(entry.get("form_id", "0"))
            suffix = f"-{form_id}" if form_id != "0" else ""
            stem = f"c_{national}{suffix}"
            species = str(entry.get("species") or "")
            # Basculegion's female appearance is represented as a separate
            # internal form ID in this Pokédex rather than gender_dimorphic.
            fixed_female_form = species.casefold() == "basculegion" and form_id == "1"
            common = {
                "species": species,
                "form_name": str(entry.get("form_name") or ""),
                "form_id": form_id,
                "national": national,
                "dex_id": str(entry.get("id") or ""),
                "gender_dimorphic": bool(entry.get("gender_dimorphic")),
                "fixed_female_form": fixed_female_form,
            }
            manifest[f"{stem}.png"] = {**common, "shiny": False, "female": fixed_female_form}
            manifest[f"{stem}s.png"] = {**common, "shiny": True, "female": fixed_female_form}
            if entry.get("gender_dimorphic"):
                manifest[f"{stem}f.png"] = {**common, "shiny": False, "female": True}
                manifest[f"{stem}fs.png"] = {**common, "shiny": True, "female": True}
        return manifest

    def _load_state(self) -> dict[str, Any]:
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return {"choice": loaded.get("choice") if loaded.get("choice") in {None, "skip", "download"} else None}
        except (OSError, json.JSONDecodeError):
            pass
        return {"choice": None}

    def _save_state(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    @staticmethod
    def _valid_png_bytes(content: bytes) -> bool:
        return (
            len(content) >= 32
            and content[:8] == b"\x89PNG\r\n\x1a\n"
            and content[-12:] == b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    @classmethod
    def _valid_png(cls, path: Path) -> bool:
        try:
            if not path.is_file() or path.stat().st_size < 32:
                return False
            with path.open("rb") as handle:
                header = handle.read(8)
                handle.seek(-12, os.SEEK_END)
                ending = handle.read(12)
            return header == b"\x89PNG\r\n\x1a\n" and ending == b"\x00\x00\x00\x00IEND\xaeB`\x82"
        except OSError:
            return False

    def _is_available(self, filename: str) -> bool:
        return any(self._valid_png(path) for path in (
            self.custom_dir / filename,
            self.legacy_custom_dir / filename,
            self.cache_dir / filename,
            self.legacy_cache_dir / filename,
        ))

    def resolve_asset(self, kind: str, filename: str) -> Path | None:
        """Resolve a safe image path, preferring user custom art over cached art."""
        if not SPRITE_NAME_RE.fullmatch(str(filename or "")):
            return None
        if kind == "custom":
            candidates = (self.custom_dir / filename, self.legacy_custom_dir / filename)
        elif kind == "cache":
            candidates = (self.cache_dir / filename, self.legacy_cache_dir / filename)
        else:
            return None
        for path in candidates:
            if self._valid_png(path):
                return path
        return None

    def _missing_files(self) -> list[str]:
        return [filename for filename in self._entries if not self._is_available(filename)]

    def status(self) -> dict[str, Any]:
        with self._lock:
            names = list(self._entries)
            custom = sum(bool(self.resolve_asset("custom", name)) for name in names)
            cached = sum(bool(self.resolve_asset("cache", name)) for name in names)
            available = sum(self._is_available(name) for name in names)
            total = len(names)
            missing = max(0, total - available)
            return {
                "ok": True,
                "total": total,
                "custom": custom,
                "cached": cached,
                "available": available,
                "missing": missing,
                "manifest_ready": total > 0,
                "complete": total > 0 and missing == 0,
                "choice": self._state.get("choice"),
                "prompt_required": total > 0 and missing > 0 and self._state.get("choice") is None,
                "custom_dir": str(self.custom_dir),
                "cache_dir": str(self.cache_dir),
                "progress": dict(self._progress),
            }

    def set_choice(self, choice: str) -> dict[str, Any]:
        if choice not in {"skip", "download"}:
            raise ValueError("图片资源选择只能是 download 或 skip。")
        with self._lock:
            self._state["choice"] = choice
            self._save_state()
        if choice == "download":
            self.start_download()
        return self.status()

    def _pokemon_slug(self, entry: dict[str, Any]) -> str:
        species = _slug(entry.get("species", ""))
        form = _slug(entry.get("form_name", ""))
        form_id = str(entry.get("form_id", "0"))
        known = {
            ("vulpix", "1"): "vulpix-alola",
            ("ninetales", "1"): "ninetales-alola",
            ("burmy", "1"): "burmy-sandy",
            ("burmy", "2"): "burmy-trash",
            ("wormadam", "1"): "wormadam-sandy",
            ("wormadam", "2"): "wormadam-trash",
            ("cherrim", "1"): "cherrim-sunshine",
            ("shellos", "1"): "shellos-east",
            ("gastrodon", "1"): "gastrodon-east",
            ("rotom", "1"): "rotom-heat",
            ("rotom", "2"): "rotom-wash",
            ("rotom", "3"): "rotom-frost",
            ("rotom", "4"): "rotom-fan",
            ("rotom", "5"): "rotom-mow",
            ("dialga", "1"): "dialga-origin",
            ("palkia", "1"): "palkia-origin",
            ("giratina", "1"): "giratina-origin",
            ("shaymin", "1"): "shaymin-sky",
            ("tornadus", "1"): "tornadus-therian",
            ("thundurus", "1"): "thundurus-therian",
            ("landorus", "1"): "landorus-therian",
            ("enamorus", "1"): "enamorus-therian",
        }
        if (species, form_id) in known:
            return known[(species, form_id)]
        if not form:
            return species
        known_suffixes = {
            "hisuian": "hisui", "alolan": "alola", "galarian": "galar",
            "paldean": "paldea", "white-striped": "white-striped",
            "blue-striped": "blue-striped", "red-striped": "red-striped",
            "origin": "origin", "therian": "therian", "sky": "sky",
            "heat": "heat", "wash": "wash", "frost": "frost", "fan": "fan", "mow": "mow",
        }
        return f"{species}-{known_suffixes.get(form, form)}"

    def _form_urls(self, entry: dict[str, Any]) -> dict[str, list[str]]:
        slug = self._pokemon_slug(entry)
        with self._lock:
            if slug in self._form_url_cache:
                return self._form_url_cache[slug]
        url = f"https://pokeapi.co/api/v2/pokemon/{slug}/"
        request = urllib.request.Request(url, headers={"User-Agent": "PLA-MMO-Path-Finder/0.7.3"})
        with urllib.request.urlopen(request, timeout=18) as response:
            payload = json.loads(response.read().decode("utf-8"))
        sprites = payload.get("sprites") or {}
        other = sprites.get("other") or {}
        home = other.get("home") or {}
        artwork = other.get("official-artwork") or {}
        normal = [value for value in (home.get("front_default"), artwork.get("front_default"), sprites.get("front_default")) if value]
        shiny = [value for value in (home.get("front_shiny"), artwork.get("front_shiny"), sprites.get("front_shiny")) if value]
        female = [value for value in (home.get("front_female"), sprites.get("front_female")) if value]
        female_shiny = [value for value in (home.get("front_shiny_female"), sprites.get("front_shiny_female")) if value]
        result = {
            "normal": normal,
            "shiny": shiny,
            "female": female or normal,
            "female_shiny": female_shiny or shiny,
        }
        with self._lock:
            self._form_url_cache[slug] = result
        return result

    def _source_urls(self, entry: dict[str, Any]) -> list[str]:
        national = int(entry["national"])
        shiny = bool(entry.get("shiny"))
        female = bool(entry.get("female"))
        form_id = str(entry.get("form_id", "0"))
        key = "female_shiny" if female and shiny else "female" if female else "shiny" if shiny else "normal"
        base = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other"
        shiny_path = "/shiny/" if shiny else "/"
        sources: list[str] = []
        if form_id != "0" or female:
            try:
                sources.extend(self._form_urls(entry).get(key) or [])
            except Exception:
                # Keep going: a missing named form must not block a safe base-art fallback.
                pass
        if form_id == "0" and not female:
            sources.extend([
                f"{base}/home{shiny_path}{national}.png",
                f"{base}/official-artwork{shiny_path}{national}.png",
            ])
        else:
            sources.extend([
                f"{base}/home{shiny_path}{national}.png",
                f"{base}/official-artwork{shiny_path}{national}.png",
            ])
        return list(dict.fromkeys(source for source in sources if source))

    def _download_one(self, filename: str) -> tuple[bool, str]:
        if not SPRITE_NAME_RE.fullmatch(filename):
            return False, f"拒绝非法图片文件名：{filename}"
        target = self.cache_dir / filename
        if self.resolve_asset("custom", filename) or self.resolve_asset("cache", filename):
            return True, ""
        if target.exists():
            try:
                target.unlink()
            except OSError:
                pass
        entry = self._entries[filename]
        errors: list[str] = []
        try:
            sources = self._source_urls(entry)
        except Exception as exc:
            return False, f"{filename}: {type(exc).__name__}: {exc}"
        for source in sources:
            try:
                request = urllib.request.Request(source, headers={"User-Agent": "PLA-MMO-Path-Finder/0.7.3"})
                with urllib.request.urlopen(request, timeout=25) as response:
                    content = response.read(4 * 1024 * 1024 + 1)
                if len(content) > 4 * 1024 * 1024:
                    raise RuntimeError("图片文件超过 4 MB，已跳过。")
                if not self._valid_png_bytes(content):
                    raise RuntimeError("素材源返回的 PNG 文件不完整或格式无效。")
                temp = target.with_suffix(target.suffix + ".tmp")
                temp.write_bytes(content)
                temp.replace(target)
                return True, ""
            except Exception as exc:
                errors.append(f"{source}: {type(exc).__name__}: {exc}")
        return False, f"{filename}: 所有素材源均失败。" + "；".join(errors[-2:])

    def start_download(self) -> dict[str, Any]:
        with self._lock:
            if self._progress.get("status") == "downloading":
                return self.status()
            missing = self._missing_files()
            if not missing:
                self._progress = {
                    "status": "complete", "total": 0, "completed": 0,
                    "downloaded": 0, "failed": 0, "current": "图片资源已完整",
                    "errors": [], "percent": 100,
                }
                return self.status()
            self._progress = {
                "status": "downloading", "total": len(missing), "completed": 0,
                "downloaded": 0, "failed": 0, "current": "正在准备图片资源…",
                "errors": [], "percent": 0,
            }
            self._worker = threading.Thread(target=self._run_download, args=(missing,), daemon=True)
            self._worker.start()
            return self.status()

    def _run_download(self, missing: list[str]) -> None:
        errors: list[str] = []
        downloaded = 0
        completed = 0
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(self._download_one, name): name for name in missing}
            for future in as_completed(futures):
                filename = futures[future]
                try:
                    success, error = future.result()
                except Exception as exc:  # defensive boundary for worker failures
                    success, error = False, f"{filename}: {type(exc).__name__}: {exc}"
                completed += 1
                if success:
                    downloaded += 1
                elif error:
                    errors.append(error)
                with self._lock:
                    self._progress.update({
                        "completed": completed,
                        "downloaded": downloaded,
                        "failed": len(errors),
                        "current": filename,
                        "errors": errors[-20:],
                        "percent": int(completed * 100 / max(1, len(missing))),
                    })
        with self._lock:
            missing_after = self._missing_files()
            self._progress.update({
                "status": "complete" if not missing_after else "partial",
                "current": "图片资源已就绪" if not missing_after else "部分图片未能下载，可重试缺失资源",
                "percent": 100 if not missing_after else int(completed * 100 / max(1, len(missing))),
                "failed": len(missing_after),
                "errors": errors[-20:],
            })

    def open_custom_folder(self) -> dict[str, Any]:
        folder = str(self.custom_dir.resolve())
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
            return {"ok": True, "path": folder, "opened": True}
        except Exception as exc:
            return {"ok": True, "path": folder, "opened": False, "message": str(exc)}
