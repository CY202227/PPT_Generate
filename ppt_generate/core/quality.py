"""Conservative machine gates: evidence matching never certifies factual accuracy."""

import hashlib
import re
from decimal import Decimal

from .editorial import _body


def _numbers(text):
    return {
        Decimal(x.replace(",", ""))
        for x in re.findall(
            r"(?<![A-Za-z0-9_.])-?\d+(?:,\d{3})*(?:\.\d+)?(?![A-Za-z0-9_]|\.\d)", text
        )
    }


def audit_numbers(deck, source, derived_paths=()):
    """Detect unsupported literals; relationships, units and derived values need review."""
    available = _numbers(source)
    issues = []
    checked = 0
    for page, slide in enumerate(deck["slides"], 1):
        values = _numbers(" ".join([slide["title"], *_body(slide)]))
        unsupported = bool(values - available)
        if slide["layout"] == "chart":
            for series, item in enumerate(slide["series"]):
                for category, value in enumerate(item["values"]):
                    number = Decimal(str(value))
                    values.add(number)
                    path = f"/slides/{page - 1}/series/{series}/values/{category}"
                    if number not in available and path not in derived_paths:
                        unsupported = True
        checked += len(values)
        if unsupported:
            issues.append(
                {
                    "page": page,
                    "code": "unsupported_numeric_literal",
                    "message": "Numeric literals absent from supplied material; correct or supply derivation",
                }
            )
    return {
        "status": "issues_found" if issues else "literal_checks_passed",
        "issues": issues,
        "checked_literals": checked,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "factual_accuracy": "not_verified",
        "limitations": [
            "Number presence does not verify metric, unit, period or meaning; derived values require manual review."
        ],
    }


def delivery_gate(quality):
    blocked = [
        name
        for name in ("editorial", "evidence", "provenance", "layout")
        if quality.get(name, {}).get("status") == "issues_found"
    ]
    reviews = quality.get("reviews", {})
    pending = [
        name
        for name in ("factual_review", "visual_review")
        if reviews.get(name, {}).get("decision") != "approved"
    ]
    blocked.extend(name for name, record in reviews.items() if record.get("decision") == "rejected")
    if quality.get("provenance", {}).get("status") == "incomplete":
        pending.append("evidence_bindings")
    if "evidence" not in quality:
        pending.append("source_checks")
    if "layout" not in quality:
        pending.append("engine_preview")
    return {
        "status": "blocked" if blocked else "needs_review" if pending else "ready",
        "blocked_by": blocked,
        "pending": pending,
        "ready": not blocked and not pending,
    }
