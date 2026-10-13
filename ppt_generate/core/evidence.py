"""Exact, auditable chart/source bindings; semantic judgement stays with a reviewer."""

import re
from decimal import Decimal

from .calculations import audit_calculation
from .quality import _numbers


def get_evidence_schema():
    def obj(properties, required):
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    text = {"type": "string", "minLength": 1, "maxLength": 60}
    location = {
        "start": {"type": "integer", "minimum": 0},
        "quote": {"type": "string", "minLength": 1, "maxLength": 2000},
    }
    operand = obj(
        {
            **location,
            "value": {
                "oneOf": [{"type": "number"}, {"type": "string", "minLength": 1, "maxLength": 64}]
            },
            "category": text,
            "unit": text,
            "period": text,
        },
        ["start", "quote", "value", "category", "unit", "period"],
    )
    derivation = obj(
        {
            "operation": {
                "enum": ["sum", "difference", "ratio", "percentage", "percentage_change"]
            },
            "precision": {"type": "integer", "minimum": 0, "maximum": 6},
            "inputs": {"type": "array", "minItems": 2, "maxItems": 8, "items": operand},
        },
        ["operation", "precision", "inputs"],
    )
    derivation["allOf"] = [
        {
            "if": {
                "properties": {
                    "operation": {
                        "enum": ["difference", "ratio", "percentage", "percentage_change"]
                    }
                }
            },
            "then": {"properties": {"inputs": {"maxItems": 2}}},
        }
    ]
    path = {"type": "string", "pattern": r"^/slides/\d+/series/\d+/values/\d+$"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "maxItems": 960,
        "items": {
            "oneOf": [
                obj({"path": path, **location}, ["path", "start", "quote"]),
                obj({"path": path, "derivation": derivation}, ["path", "derivation"]),
            ]
        },
    }


def audit_bindings(deck, source, bindings):
    if not isinstance(bindings, list) or len(bindings) > 960:
        raise ValueError("bindings must be a list of at most 960 chart value references")
    expected = {}
    for page, slide in enumerate(deck["slides"]):
        if slide["layout"] == "chart":
            for series, item in enumerate(slide["series"]):
                for category, value in enumerate(item["values"]):
                    path = f"/slides/{page}/series/{series}/values/{category}"
                    expected[path] = (
                        value,
                        item["name"],
                        slide["categories"][category],
                        slide["unit"],
                        slide["period"],
                    )
    issues, references, seen = [], [], set()
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) not in (
            {"path", "start", "quote"},
            {"path", "derivation"},
        ):
            raise ValueError("Binding requires path/start/quote or path/derivation")
        path = binding["path"]
        if not isinstance(path, str) or path not in expected or path in seen:
            raise ValueError("Binding path must uniquely identify a chart value")
        seen.add(path)
        if "derivation" in binding:
            codes, calculation = audit_calculation(source, binding["derivation"], expected[path])
            issues.extend(
                {"page": int(path.split("/")[2]) + 1, "path": path, "code": code} for code in codes
            )
            references.append(
                {
                    "path": path,
                    "calculation": calculation,
                    "status": "issues_found" if codes else "calculation_checks_passed",
                }
            )
            continue
        start, quote = binding["start"], binding["quote"]
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or start < 0
            or not isinstance(quote, str)
            or not quote.strip()
            or len(quote) > 2000
        ):
            raise ValueError("Binding needs a nonnegative source offset and bounded quote")
        value, metric, category, unit, period = expected[path]
        codes = []
        if source[start : start + len(quote)] != quote:
            codes.append("source_quote_mismatch")
        if Decimal(str(value)) not in _numbers(quote):
            codes.append("bound_value_missing")
        normalized = re.sub(r"\s+", " ", quote).casefold()
        # Exact terminology prevents silently treating a same-valued unrelated metric as evidence.
        for label, text in (
            ("metric", metric),
            ("category", category),
            ("unit", unit),
            ("period", period),
        ):
            if re.sub(r"\s+", " ", text).casefold() not in normalized:
                codes.append(f"bound_{label}_missing")
        issues.extend(
            {"page": int(path.split("/")[2]) + 1, "path": path, "code": code} for code in codes
        )
        references.append(
            {
                "path": path,
                "source_start": start,
                "source_end": start + len(quote),
                "status": "issues_found" if codes else "context_checks_passed",
            }
        )
    missing = sorted(set(expected) - seen)
    return {
        "status": "issues_found"
        if issues
        else "incomplete"
        if missing
        else "context_checks_passed",
        "issues": issues,
        "references": references,
        "missing_paths": missing,
        "factual_accuracy": "not_verified",
        "limitations": [
            "Exact context and whitelisted decimal calculations are checked, not semantic relationships or translations; human factual review remains required."
        ],
    }
