"""Versioned, validated slide interchange format for upstream agents."""

import json
import math
from importlib.resources import files

from jsonschema import Draft202012Validator


def get_schema():
    return json.loads(
        files("ppt_generate.resources").joinpath("deck.schema.json").read_text(encoding="utf-8")
    )


LAYOUTS = {"cover", "bullets", "table", "chart", "split", "kpi", "timeline"}


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonempty text of at most {limit} characters")


def validate_deck(deck):
    errors = sorted(
        Draft202012Validator(get_schema()).iter_errors(deck),
        key=lambda error: str(list(error.path)),
    )
    if errors:
        error = errors[0]
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        # Do not echo user document text into errors.
        raise ValueError(f"Invalid deck at {location}: schema constraint {error.validator}")
    if not isinstance(deck, dict) or deck.get("schema_version") != "1.0":
        raise ValueError("schema_version must be 1.0")
    _text(deck.get("title"), "title", 80)
    slides = deck.get("slides")
    if not isinstance(slides, list) or not 1 <= len(slides) <= 40:
        raise ValueError("slides must contain 1–40 pages")
    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            raise ValueError(f"slide {i} must be an object")
        _text(slide.get("title"), f"slide {i} title", 44)
        layout = slide.get("layout")
        if layout not in LAYOUTS:
            raise ValueError(f"slide {i}: unsupported layout")
        for field, limit in [("notes", 6000), ("source", 300), ("subtitle", 150)]:
            if field in slide:
                _text(slide[field], field, limit)
        if layout == "bullets":
            _items(slide.get("bullets"), 6, 110)
        if layout == "split":
            columns = slide.get("columns")
            if not isinstance(columns, list) or len(columns) != 2:
                raise ValueError("split requires exactly two columns")
            for col in columns:
                if not isinstance(col, dict):
                    raise ValueError("columns must be objects")
                _text(col.get("heading"), "column heading", 24)
                _items(col.get("bullets"), 4, 70)
        if layout == "table":
            headers, rows = slide.get("headers"), slide.get("rows")
            _items(headers, 6, 24)
            if not isinstance(rows, list) or not 1 <= len(rows) <= 7:
                raise ValueError("table requires 1–7 rows")
            for row in rows:
                if not isinstance(row, list) or len(row) != len(headers):
                    raise ValueError("table row width must match headers")
                for cell in row:
                    _text(cell, "table cell", 36)
        if layout == "chart":
            _items(slide.get("categories"), 8, 20)
            _text(slide.get("unit"), "chart unit", 24)
            _text(slide.get("period"), "chart period", 60)
            if slide.get("chart_type", "column") not in {"column", "line"}:
                raise ValueError("chart_type must be column or line")
            series = slide.get("series")
            if not isinstance(series, list) or not 1 <= len(series) <= 3:
                raise ValueError("chart requires 1–3 series")
            for s in series:
                if not isinstance(s, dict):
                    raise ValueError("series must be objects")
                _text(s.get("name"), "series name", 30)
                values = s.get("values")
                if not isinstance(values, list) or len(values) != len(slide["categories"]):
                    raise ValueError("series length must match categories")
                if any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in values
                ):
                    raise ValueError("chart values must be finite numbers")
    return deck


def _items(items, count, limit):
    if not isinstance(items, list) or not 1 <= len(items) <= count:
        raise ValueError(f"expected 1–{count} text items")
    for item in items:
        _text(item, "item", limit)
