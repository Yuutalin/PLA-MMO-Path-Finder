from __future__ import annotations

import importlib
import importlib.util
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pla_mmo.paths import get_project_root

PROJECT_ROOT = get_project_root()
APP_VERSION = "0.3.6"
ENGINE_ROOT = PROJECT_ROOT / "offline_engine"
RESOURCE_ROOT = ENGINE_ROOT / "static" / "resources"
MANIFEST_PATH = ENGINE_ROOT / "engine_manifest.json"
ENGINE_OK_PATH = ENGINE_ROOT / "engine_install_ok.txt"
SPECIES_ZH_PATH = Path(__file__).with_name("species_zh.json")
POKEDEX_PATH = RESOURCE_ROOT / "pokedex.json"
SEEDHASHES_PATH = RESOURCE_ROOT / "seedhashes.json"
HISUI_DEX_PATH = RESOURCE_ROOT / "hisuidex.txt"
ENCOUNTERS_PATH = RESOURCE_ROOT / "mmo_es.json"
REQUIRED_RESOURCES = (
    "mmo_es.json",
    "mmopaths.json",
    "nonbonuspaths.json",
)


@lru_cache(maxsize=1)
def _load_species_names_zh() -> dict[str, str]:
    try:
        data = json.loads(SPECIES_ZH_PATH.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def translate_species_name(name: Any) -> str:
    """Return a stable Simplified-Chinese name for species and internal form IDs."""
    raw = str(name or "").strip()
    if not raw:
        return raw
    mapping = _load_species_names_zh()
    if raw in mapping:
        return mapping[raw]
    folded = raw.casefold()
    for key, value in mapping.items():
        if key.casefold() == folded:
            return value
    if raw.startswith("Alpha "):
        return "头目" + translate_species_name(raw[6:])
    prefixes = (
        ("Hisuian ", "洗翠"),
        ("Alolan ", "阿罗拉"),
        ("Galarian ", "伽勒尔"),
        ("Paldean ", "帕底亚"),
        ("White-Striped ", "白条纹"),
    )
    for prefix, localized in prefixes:
        if raw.startswith(prefix):
            return localized + translate_species_name(raw[len(prefix):])
    # The local engine uses internal suffixes such as Growlithe-1 and MimeJr.
    # Exact form aliases are in species_zh.json; unknown numeric forms should
    # still be localized rather than leaking raw English into the interface.
    match = re.match(r"^(.+)-(\d+)$", raw)
    if match:
        base, form_id = match.groups()
        base_zh = translate_species_name(base)
        return f"{base_zh}（特殊形态）"
    if raw == "MimeJr.":
        return mapping.get("MimeJr.", "魔尼尼")
    if raw == "Mr.Mime":
        return mapping.get("Mr.Mime", "魔墙人偶")
    return raw


class LocalEngineError(RuntimeError):
    """The local RNG engine is unavailable or its data is invalid."""


def _strip_html(value: Any) -> str:
    return re.sub(r"<[^>]*>", "", str(value or "")).replace("&nbsp;", " ").strip()


def _normalise_hash(value: Any) -> str:
    text = str(value or "").strip()
    return text[2:] if text.lower().startswith("0x") else text


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "shiny", "alpha"}
    return False


def _walk_results(node: Any):
    """Flatten the original engine's nested MMO/path dictionaries."""
    if isinstance(node, dict):
        if "species" in node and "shiny" in node and "index" in node:
            yield node
            return
        for child in node.values():
            yield from _walk_results(child)
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from _walk_results(child)


def _matches_filter(item: dict, filter_name: str) -> bool:
    shiny = _as_bool(item.get("shiny"))
    square = _as_bool(item.get("square"))
    alpha = _as_bool(item.get("alpha"))
    ivs = item.get("ivs")
    if not isinstance(ivs, (list, tuple)) or len(ivs) != 6:
        ivs = []

    perfect = len(ivs) == 6 and all(int(v) == 31 for v in ivs)
    iv31 = sum(int(v) == 31 for v in ivs) if ivs else 0
    iv30 = sum(int(v) >= 30 for v in ivs) if ivs else 0
    attack_zero = len(ivs) == 6 and int(ivs[1]) == 0
    speed_zero = len(ivs) == 6 and int(ivs[5]) == 0

    checks = {
        "is_shiny": shiny,
        "is_square_shiny": shiny and square,
        "is_alpha": alpha,
        "is_perfect": perfect,
        "has_5ivs": iv31 >= 5,
        "no_attack": attack_zero,
        "has_no_attack_5iv_over_30": attack_zero and iv30 >= 5,
        "has_no_attack_5iv": attack_zero and iv31 >= 5,
        "no_speed": speed_zero,
        "has_no_speed_5iv_over_30": speed_zero and iv30 >= 5,
        "has_no_speed_5iv": speed_zero and iv31 >= 5,
        "has_6iv_over_30": iv30 == 6,
        "has_5iv_over_30": iv30 >= 5,
        "has_no_speed_no_attack": speed_zero and attack_zero,
        "has_no_speed_no_attack_4iv_over_30": speed_zero and attack_zero and iv30 >= 4,
        "has_no_speed_no_attack_4iv": speed_zero and attack_zero and iv31 >= 4,
    }
    if filter_name not in checks:
        raise LocalEngineError(f"不支持的本地过滤条件：{filter_name}")
    return checks[filter_name]


@lru_cache(maxsize=1)
def _load_dex_sprite_index() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(POKEDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, list):
        return {}
    return {
        str(entry.get("id", "")).casefold(): entry
        for entry in data
        if isinstance(entry, dict) and entry.get("id")
    }


def sprite_for_species(name: Any) -> str:
    """Find the local engine sprite filename for a candidate species/form."""
    raw = str(name or "").strip()
    if raw.startswith("Alpha "):
        raw = raw[6:].strip()
    aliases = {"MimeJr.": "Mime Jr.", "Mr.Mime": "Mr. Mime"}
    raw = aliases.get(raw, raw)
    entry = _load_dex_sprite_index().get(raw.casefold())
    if not entry:
        return ""
    national = int(entry.get("dex_national") or 0)
    if national <= 0:
        return ""
    form_id = str(entry.get("form_id") or "0")
    suffix = f"-{form_id}" if form_id != "0" else ""
    return f"c_{national}{suffix}.png"


class LocalMMOEngine:
    """Adapter for the vendored PLA MMO RNG implementation.

    The engine and encounter tables are installed into ./offline_engine once.
    Calculation never calls an external HTTP API.
    """

    def __init__(self):
        self._encounter_tables: dict | None = None
        self._manifest: dict | None = None

    def _read_manifest(self) -> dict:
        if self._manifest is not None:
            return self._manifest
        try:
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            self._manifest = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            self._manifest = {}
        return self._manifest

    def status(self) -> dict:
        missing = []
        if not (ENGINE_ROOT / "pla" / "checkmmo.py").is_file():
            missing.append("本地 MMO 计算代码")
        if not (ENGINE_ROOT / "app" / "__init__.py").is_file():
            missing.append("本地引擎资源路径适配器")
        for name in REQUIRED_RESOURCES:
            if not (RESOURCE_ROOT / name).is_file():
                missing.append(name)
        if not SEEDHASHES_PATH.is_file():
            missing.append("seedhashes.json（候选列表）")

        dependency_status = {"z3_solver": False, "z3_version": "", "pyusb": False}
        dependency_errors = []
        try:
            z3_module = importlib.import_module("z3")
            dependency_status["z3_solver"] = True
            dependency_status["z3_version"] = z3_module.get_version_string()
        except Exception as exc:
            dependency_errors.append(f"z3-solver 不可用（{type(exc).__name__}: {exc}）")
        try:
            importlib.import_module("usb")
            dependency_status["pyusb"] = True
        except Exception as exc:
            dependency_errors.append(f"pyusb 不可用（{type(exc).__name__}: {exc}）")
        if dependency_errors:
            missing.extend("Python 依赖 " + item for item in dependency_errors)

        manifest = self._read_manifest()
        installed = not missing
        manifest_version = str(manifest.get("app_version") or "")
        verified = installed and ENGINE_OK_PATH.is_file() and manifest_version == APP_VERSION
        return {
            "installed": installed,
            "verified": verified,
            "engine": "PLA MMO 本地 RNG 引擎" if verified else ("本地引擎文件已安装，尚未验证" if installed else "尚未安装"),
            "version": str(manifest.get("upstream_commit") or manifest.get("installed_at") or "未记录"),
            "app_version": manifest_version or "未记录",
            "source": "capitalism-sudo/pla-multi-checker-web",
            "license": "GPL-3.0",
            "mapping_complete": bool(manifest.get("candidate_mapping_complete", False)),
            "candidate_source": str(manifest.get("candidate_source") or "未安装"),
            "dependencies": dependency_status,
            "missing": missing,
            "message": (
                "本地引擎和必要资源已通过实际计算测试；计算请求在本机处理。"
                if verified
                else (
                    (
                        f"本地引擎验证版本为 {manifest_version or '未记录'}，当前程序要求 {APP_VERSION}；"
                        "请运行 prepare_offline_engine.bat 重新验证。"
                        if manifest_version != APP_VERSION
                        else "本地引擎文件存在，但尚未通过实际计算测试。请运行 prepare_offline_engine.bat。"
                    )
                    if installed
                    else "本地计算引擎尚未就绪。问题：" + "；".join(missing)
                    + "。请运行 prepare_offline_engine.bat 修复。"
                )
            ),
        }

    def _load_encounter_tables(self) -> dict:
        if self._encounter_tables is not None:
            return self._encounter_tables
        if not ENCOUNTERS_PATH.is_file():
            raise LocalEngineError(
                "找不到本地遭遇表 mmo_es.json。请运行 prepare_offline_engine.bat 修复本地引擎。"
            )
        try:
            data = json.loads(ENCOUNTERS_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalEngineError(f"本地遭遇表无法读取：{exc}")
        if not isinstance(data, dict) or not data:
            raise LocalEngineError("本地遭遇表格式无效或内容为空。")
        self._encounter_tables = data
        return data

    def _resolve_table_hash(self, value: Any) -> str:
        tables = self._load_encounter_tables()
        raw = str(value or "").strip()
        if raw in tables:
            return raw
        normalized = _normalise_hash(raw).lower()
        matches = [
            key for key in tables
            if _normalise_hash(key).lower() == normalized
        ]
        if len(matches) == 1:
            return matches[0]
        if not raw:
            raise LocalEngineError("没有选择有效的遭遇表。")
        raise LocalEngineError(
            f"所选遭遇表 {raw} 不存在于本地资源中。候选列表和计算资源可能不是同一版本，请重新运行 prepare_offline_engine.bat。"
        )

    def load_species(self) -> dict:
        status = self.status()
        if not status["installed"]:
            raise LocalEngineError(status["message"])

        raw_data = None
        try:
            raw_data = json.loads(SEEDHASHES_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            raw_data = None

        if isinstance(raw_data, dict):
            if isinstance(raw_data.get("species"), list):
                raw_data = raw_data["species"]
            else:
                raw_data = list(raw_data.values())

        normalized = []
        if isinstance(raw_data, list):
            for item in raw_data:
                if not isinstance(item, dict):
                    continue
                species = item.get("species")
                species_hash = item.get("hash")
                if species is None or species_hash is None:
                    continue
                species_text = str(species)
                raw_label = str(item.get("label") or species_text)
                normalized.append({
                    "species": species_text,
                    "species_zh": translate_species_name(species_text),
                    "label": translate_species_name(raw_label),
                    "label_en": raw_label,
                    "hash": str(species_hash),
                    "parent_id": str(item.get("parent_id", "")),
                    "sprite": sprite_for_species(species_text),
                })

        if not normalized:
            raise LocalEngineError(
                "本地候选列表为空或格式不正确。请运行 prepare_offline_engine.bat 重新安装资源。"
            )

        # Reject stale candidate hashes instead of allowing a crash inside the RNG engine.
        tables = self._load_encounter_tables()
        table_norms = {_normalise_hash(k).lower() for k in tables}
        valid = [
            item for item in normalized
            if _normalise_hash(item["hash"]).lower() in table_norms
        ]
        if not valid:
            raise LocalEngineError(
                "候选列表与本地遭遇表完全不匹配。请运行 prepare_offline_engine.bat 重新安装同一版本的代码和数据。"
            )

        mapping_complete = status["mapping_complete"] and len(valid) == len(normalized)
        warning_parts = []
        if not status["mapping_complete"]:
            warning_parts.append(
                "当前使用本地生成的候选列表，原版第一轮/奖励轮对应关系数据未取得。"
                "计算算法仍在本机运行，但奖励轮下拉框会列出全部遭遇表，请按实际群体选择。"
            )
        if len(valid) != len(normalized):
            warning_parts.append(
                f"已忽略 {len(normalized) - len(valid)} 个与本地遭遇表不匹配的候选项，"
                "候选数据映射可能不完整；可运行 prepare_offline_engine.bat 重新获取资源。"
            )
        return {
            "species": valid,
            "name_map": _load_species_names_zh(),
            "source": "local",
            "mapping_complete": mapping_complete,
            "warning": " ".join(warning_parts) if warning_parts else None,
        }

    def load_research_catalog(self) -> dict:
        """Return the Hisui Pokédex in its in-game evolution-line order.

        This catalog intentionally does not depend on the RNG engine being
        installed: research-level preferences can be edited before first setup.
        The species IDs match the local engine's internal species/form keys.
        """
        try:
            dex_entries = json.loads(POKEDEX_PATH.read_text(encoding="utf-8"))
            dex_by_id = {
                str(entry.get("id", "")).strip(): entry
                for entry in dex_entries
                if isinstance(entry, dict) and entry.get("id")
            } if isinstance(dex_entries, list) else {}
            lines = HISUI_DEX_PATH.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalEngineError(f"无法读取洗翠图鉴数据：{exc}") from exc

        catalog = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            try:
                dex_number = int(parts[0].strip())
            except ValueError:
                continue
            species_id = parts[1].strip()
            if not species_id:
                continue
            dex_entry = dex_by_id.get(species_id, {})
            label = translate_species_name(species_id)
            # A few regional forms are represented by a numeric internal ID.
            # The Chinese-name table contains those IDs directly; this fallback
            # handles older resource packs that only include form metadata.
            if not label or label == species_id:
                base_name = str(dex_entry.get("species") or species_id)
                form_name = str(dex_entry.get("form_name") or "").strip()
                if form_name == "Hisuian":
                    label = translate_species_name(f"Hisuian {base_name}")
                elif form_name == "White-Striped":
                    label = translate_species_name(f"White-Striped {base_name}")
                else:
                    label = translate_species_name(base_name)
            catalog.append({
                "dex_number": dex_number,
                "species": species_id,
                "label": label,
                "label_en": species_id,
                "sprite": sprite_for_species(species_id),
            })

        if not catalog:
            raise LocalEngineError("洗翠图鉴数据为空，无法加载宝可梦研究等级列表。")
        return {"species": catalog, "total": len(catalog), "source": "local"}

    def calculate_mmo_path(self, seed: str, params: dict) -> dict:
        status = self.status()
        if not status["installed"]:
            raise LocalEngineError(status["message"])

        first_hash = self._resolve_table_hash(params.get("frencounter"))
        bonus = bool(params.get("isbonus"))
        second_hash = self._resolve_table_hash(params.get("brencounter")) if bonus else ""
        if bonus and not second_hash:
            raise LocalEngineError("启用奖励轮时必须选择有效的奖励轮遭遇表。")

        try:
            # Import under the vendored package name so `from ..app import
            # RESOURCE_PATH` resolves to offline_engine.app, not top-level pla.
            module = importlib.import_module("offline_engine.pla.checkmmo")
            check_mmo_from_seed = getattr(module, "check_mmo_from_seed")
            # Mirror the upstream project's research payload contract:
            # {"shinycharm": bool, "rolls": {species: extra_rolls}}.
            # Migrate legacy flat payloads from v0.3.0/v0.3.1 at the boundary,
            # so even old saved callers cannot trigger KeyError("rolls").
            incoming_research = dict(params.get("research") or {})
            shinycharm = _as_bool(
                incoming_research.get("shinycharm", params.get("shiny_charm", False))
            )
            raw_rolls = incoming_research.get("rolls")
            if isinstance(raw_rolls, dict):
                species_rolls = dict(raw_rolls)
            else:
                species_rolls = {
                    str(key): value
                    for key, value in incoming_research.items()
                    if key not in {"shinycharm", "rolls"}
                }
            research = {"shinycharm": shinycharm, "rolls": species_rolls}
            raw = check_mmo_from_seed(
                int(str(seed)),
                research,
                first_hash,
                second_hash,
                bonus,
                int(params["frspawns"]),
                int(params["brspawns"]),
                bool(params["isnormal"]),
            )
        except LocalEngineError:
            raise
        except Exception as exc:
            raise LocalEngineError(
                f"本地 RNG 引擎计算失败：{type(exc).__name__}: {exc}。"
                "本次未生成替代结果；请检查参数和本地资源版本。"
            ) from exc

        filter_name = str(params.get("filter", "is_shiny"))
        results = []
        seen = set()
        for original in _walk_results(raw):
            if not _matches_filter(original, filter_name):
                continue
            item = dict(original)
            item["path"] = _strip_html(item.get("index", ""))
            item["default_path"] = bool(item.get("defaultroute", False))
            # Alternative routes (`dupes`) do not mean multiple simultaneous
            # shiny encounters. Keep this compatibility field semantically narrow.
            item["multi_path"] = bool(item.get("multi", False) or item.get("multi_shiny", False) or item.get("multi_shiny_path", False) or item.get("chains"))
            item["species"] = str(item.get("species") or "未知宝可梦")
            for key in ("chains", "dupes"):
                value = item.get(key)
                if isinstance(value, list):
                    item[key] = [_strip_html(part) for part in value]
                elif value is not None:
                    item[key] = _strip_html(value)
            for key in ("ec", "pid", "generator_seed"):
                value = item.get(key)
                if isinstance(value, int):
                    item[f"{key}_hex"] = f"{value:016X}" if key == "generator_seed" else f"{value:08X}"
            # Deduplicate exact records if the original path tree references the same
            # spawn more than once; keep path variants in the 'dupes'/'chains' fields.
            dedupe_key = (
                str(item.get("species")), str(item.get("ec")), str(item.get("pid")),
                str(item.get("path")), bool(item.get("shiny")), bool(item.get("alpha"))
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            results.append(item)

        return {
            "results": results,
            "engine": "PLA MMO Checker 本地 RNG 引擎",
            "summary": {"result_count": len(results), "returned_empty": not results},
        }
