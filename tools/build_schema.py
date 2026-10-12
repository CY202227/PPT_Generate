"""Generate the public schema deterministically; no external service required."""

import json
from pathlib import Path


def text(limit):
    return {"type": "string", "minLength": 1, "maxLength": limit, "pattern": "\\S"}


def items(item, limit):
    return {"type": "array", "minItems": 1, "maxItems": limit, "items": item}


def obj(properties, required):
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


common = {"title": text(44), "source": text(300), "notes": text(6000)}
layouts = {
    "kpi": (
        {
            "metrics": items(
                obj({"label": text(24), "value": text(24), "detail": text(70)}, ["label", "value"]),
                3,
            )
        },
        ["metrics"],
    ),
    "timeline": (
        {
            "events": items(
                obj(
                    {"date": text(20), "heading": text(24), "detail": text(90)},
                    ["date", "heading", "detail"],
                ),
                4,
            )
        },
        ["events"],
    ),
    "cover": ({"subtitle": text(150)}, []),
    "bullets": ({"bullets": items(text(110), 6)}, ["bullets"]),
    "split": (
        {
            "columns": {
                **items(
                    obj(
                        {"heading": text(24), "bullets": items(text(70), 4)}, ["heading", "bullets"]
                    ),
                    2,
                ),
                "minItems": 2,
            }
        },
        ["columns"],
    ),
    "table": (
        {"headers": items(text(24), 6), "rows": items(items(text(36), 6), 7)},
        ["headers", "rows"],
    ),
    "chart": (
        {
            "chart_type": {"enum": ["column", "line"]},
            "unit": text(24),
            "period": text(60),
            "categories": items(text(20), 8),
            "series": items(
                obj({"name": text(30), "values": items({"type": "number"}, 8)}, ["name", "values"]),
                3,
            ),
        },
        ["unit", "period", "categories", "series"],
    ),
}
definitions = {
    name: obj({**common, "layout": {"const": name}, **props}, ["layout", "title", *required])
    for name, (props, required) in layouts.items()
}
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "PPT Generate Deck v1.0",
    **obj(
        {
            "schema_version": {"const": "1.0"},
            "title": text(80),
            "slides": items({"oneOf": [{"$ref": f"#/$defs/{name}"} for name in layouts]}, 40),
        },
        ["schema_version", "title", "slides"],
    ),
    "$defs": definitions,
}
if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "ppt_generate/resources/deck.schema.json"
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
