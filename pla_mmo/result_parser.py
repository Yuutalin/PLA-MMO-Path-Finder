from __future__ import annotations


def result_count(results) -> int:
    if isinstance(results, list):
        return len(results)
    if isinstance(results, dict):
        return len(results)
    return 0


def find_first_value(item: dict, aliases: tuple[str, ...]):
    if not isinstance(item, dict):
        return None
    lowered = {str(key).lower(): value for key, value in item.items()}
    for alias in aliases:
        if alias.lower() in lowered:
            return lowered[alias.lower()]
    return None


def summarize_item(item) -> dict:
    if not isinstance(item, dict):
        return {"title": str(item), "fields": {}}
    title = find_first_value(item, ("species", "pokemon", "name", "encounter", "mon"))
    area = find_first_value(item, ("map", "map_name", "mapname", "location", "area"))
    shiny = find_first_value(item, ("is_shiny", "shiny", "isshiny", "shiny_status"))
    alpha = find_first_value(item, ("is_alpha", "alpha", "isalpha", "isAlpha"))
    path = find_first_value(item, ("path", "paths", "route", "default_path", "defaultpath", "default_route"))
    return {
        "title": str(title) if title is not None else "计算结果",
        "area": area,
        "shiny": shiny,
        "alpha": alpha,
        "path": path,
        "fields": item,
    }
