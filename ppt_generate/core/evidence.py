"""Exact, auditable chart/source bindings; semantic judgement stays with a reviewer."""

import re
from decimal import Decimal

from .quality import _numbers


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
        if not isinstance(binding, dict) or set(binding) != {"path", "start", "quote"}:
            raise ValueError("Each binding requires only path, start and quote")
        path, start, quote = binding["path"], binding["start"], binding["quote"]
        if not isinstance(path, str) or path not in expected or path in seen:
            raise ValueError("Binding path must uniquely identify a chart value")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or start < 0
            or not isinstance(quote, str)
            or not quote.strip()
            or len(quote) > 2000
        ):
            raise ValueError("Binding needs a nonnegative source offset and bounded quote")
        seen.add(path)
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
            "Exact contextual terms and numbers are checked, not their relationship. Translation and calculated values need explicitly matching source material and human review."
        ],
    }
