from __future__ import annotations

import re

from pla_mmo.local_engine import LocalEngineError

ALLOWED_FILTERS = {
    "is_shiny",
    "is_square_shiny",
    "is_alpha",
    "is_perfect",
    "has_5ivs",
    "no_attack",
    "has_no_attack_5iv_over_30",
    "has_no_attack_5iv",
    "no_speed",
    "has_no_speed_5iv_over_30",
    "has_no_speed_5iv",
    "has_6iv_over_30",
    "has_5iv_over_30",
    "has_no_speed_no_attack",
    "has_no_speed_no_attack_4iv_over_30",
    "has_no_speed_no_attack_4iv",
}

RESEARCH_BONUS_ROLLS = {
    # Upstream get_rolls() starts from BASE_ROLLS_MMOS and adds these values.
    # Base = +0, research level 10 = +1, perfect research = +3.
    "base": 0,
    "level10": 1,
    "perfect": 3,
}


def _nonempty_string(value, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"请选择{label}。")
    return result


def _research_species_key(name: str) -> str:
    # Alpha is an encounter-table attribute, not a separate Pokédex species.
    value = str(name or "").strip()
    if value.casefold().startswith("alpha "):
        value = value[6:].strip()
    return value


def _configured_research_level(species: str, settings: dict, fallback: str = "level10") -> str:
    default_level = str(settings.get("default_research_level") or fallback).strip()
    if default_level not in RESEARCH_BONUS_ROLLS:
        default_level = fallback if fallback in RESEARCH_BONUS_ROLLS else "level10"
    levels = settings.get("pokemon_research_levels") or {}
    key = _research_species_key(species)
    if isinstance(levels, dict):
        lookup_keys = [key]
        # Some encounter forms share one Hisui Pokédex entry. Prefer an exact
        # form override, then fall back to the base species' research level.
        form_match = re.match(r"^(.+)-\d+$", key)
        if form_match:
            lookup_keys.append(form_match.group(1))
        for lookup_key in lookup_keys:
            if lookup_key in levels and str(levels[lookup_key]) in RESEARCH_BONUS_ROLLS:
                return str(levels[lookup_key])
            folded = lookup_key.casefold()
            for stored_key, stored_level in levels.items():
                if str(stored_key).strip().casefold() == folded and str(stored_level) in RESEARCH_BONUS_ROLLS:
                    return str(stored_level)
    return default_level


def build_calculation_params(body: dict, settings: dict | None = None) -> dict:
    first_hash = _nonempty_string(body.get("frencounter"), "第一轮宝可梦")
    first_species = _nonempty_string(body.get("fr_species"), "第一轮宝可梦")
    if settings is None:
        first_level = str(body.get("fr_research_level", "")).strip()
    else:
        first_level = _configured_research_level(first_species, settings)
    if first_level not in RESEARCH_BONUS_ROLLS:
        raise ValueError("请设置第一轮宝可梦的图鉴研究等级。")

    is_bonus = bool(body.get("isbonus", False))
    is_normal = bool(body.get("isnormal", False))
    shiny_charm = bool(body.get("shiny_charm", False)) if settings is None else bool(settings.get("default_shiny_charm", True))

    if is_bonus:
        second_hash = _nonempty_string(body.get("brencounter"), "奖励轮宝可梦")
        second_species = _nonempty_string(body.get("br_species"), "奖励轮宝可梦")
        if settings is None:
            second_level = str(body.get("br_research_level", "")).strip()
        else:
            second_level = _configured_research_level(second_species, settings)
        if second_level not in RESEARCH_BONUS_ROLLS:
            raise ValueError("请设置奖励轮宝可梦的图鉴研究等级。")
    else:
        # The reference page allows calculation with the bonus-round selector
        # blank when the bonus round is disabled. Keep the second-round fields
        # blank rather than inventing a second encounter.
        second_hash = ""
        second_species = ""
        second_level = ""

    if shiny_charm and (
        first_level == "base" or (is_bonus and second_level == "base")
    ):
        raise ValueError("拥有闪耀护符时，所选宝可梦至少应为图鉴研究等级 10。")

    first_key = _research_species_key(first_species)
    second_key = _research_species_key(second_species) if is_bonus else ""
    if is_bonus and first_key.casefold() == second_key.casefold() and first_level != second_level:
        raise ValueError("第一轮和奖励轮选择的是同一宝可梦（普通／头目形态共用图鉴研究进度），请设置相同研究等级。")

    # Match the upstream project's /api/read-research response exactly.
    # The upstream API sends:
    #   {"shinycharm": bool, "rolls": {species_name: extra_research_rolls}}
    # `get_rolls()` indexes research["rolls"], not top-level species keys.
    species_rolls = {first_key: RESEARCH_BONUS_ROLLS[first_level]}
    if is_bonus:
        species_rolls[second_key] = RESEARCH_BONUS_ROLLS[second_level]
    research = {"shinycharm": shiny_charm, "rolls": species_rolls}

    try:
        frspawns = int(body.get("frspawns", 0))
        brspawns = int(body.get("brspawns", 0))
    except (TypeError, ValueError):
        raise ValueError("群体生成数量必须是有效整数。")

    allowed_first = {10, 11, 12, 13, 14, 15} if is_normal else {8, 9, 10}
    if frspawns not in allowed_first:
        raise ValueError("第一轮生成数量与当前发生类型不匹配。")
    if brspawns not in {6, 7}:
        raise ValueError("奖励轮生成数量只能是 6 或 7。")

    filter_name = str(body.get("filter", "is_shiny"))
    if filter_name not in ALLOWED_FILTERS:
        raise ValueError("不支持的计算过滤条件。")

    return {
        "filter": filter_name,
        "research": research,
        "frencounter": first_hash,
        "brencounter": second_hash,
        "isbonus": is_bonus,
        "frspawns": frspawns,
        "brspawns": brspawns,
        "isnormal": is_normal,
        "research_levels": {
            first_key: first_level,
            **({second_key: second_level} if is_bonus else {}),
        },
        "shiny_charm": shiny_charm,
        "fr_species": first_species,
        "br_species": second_species if is_bonus else None,
    }


def calculate_mmo_path(client, seed: str, params: dict) -> dict:
    response = client.calculate_mmo_path(seed, params)
    results = response["results"]
    if not isinstance(results, (list, dict)):
        raise LocalEngineError("本地引擎的 results 字段不是列表或对象，无法展示。")
    count = len(results)
    if isinstance(results, dict):
        count = len(results.keys())
    return {
        "results": results,
        "summary": {
            "result_count": count,
            "returned_empty": count == 0,
        },
        "engine": "PLA MMO Checker 本地 RNG 引擎",
    }
