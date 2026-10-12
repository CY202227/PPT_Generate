"""Explainable editorial checks, not semantic or factual certification."""

import re
from difflib import SequenceMatcher

_INSTRUCTIONS = re.compile(
    r"(?:不(?:要|得|允许)?(?:编造|添加未提供)|(?:返回|输出)(?:合法|有效)?\s*JSON|"
    r"必须(?:严格)?(?:遵循|符合)(?:大纲|schema|格式)|"
    r"\b(?:return|output)\s+(?:only\s+)?(?:a\s+)?(?:valid\s+)?JSON\b|"
    r"\b(?:do not|never)\s+(?:invent|fabricate|add unprovided)\b)",
    re.IGNORECASE,
)
_DISCLOSURE = re.compile(
    r"来源|source|模拟数据|全部.*模拟|所有.*模拟|不添加未提供|面向.*管理层|"
    r"all.*simulated|synthetic.*ledger|simulated.*data",
    re.IGNORECASE,
)
_SUMMARY = re.compile(r"摘要|总结|summary|conclusion", re.IGNORECASE)


def _body(slide):
    if slide["layout"] == "kpi":
        return [text for metric in slide["metrics"] for text in metric.values()]
    if slide["layout"] == "timeline":
        return [text for event in slide["events"] for text in event.values()]
    if slide["layout"] == "bullets":
        return slide["bullets"]
    if slide["layout"] == "split":
        return [part for col in slide["columns"] for part in [col["heading"], *col["bullets"]]]
    if slide["layout"] == "table":
        return [*slide["headers"], *(cell for row in slide["rows"] for cell in row)]
    if slide["layout"] == "chart":
        return [*slide["categories"], *(s["name"] for s in slide["series"])]
    return []


def _normalized(text):
    return re.sub(r"[\W_]", "", text.casefold())


def review_editorial(deck):
    """Return location-based issues without copying private slide text into diagnostics.

    Rules may flag legitimate instructional decks; direct rendering records findings instead
    of deleting/rejecting supplied content. Model planning uses the same rules for repair.
    """
    issues = []

    def issue(page, code, message, related=None):
        item = {"page": page, "code": code, "severity": "warning", "message": message}
        if related:
            item["related_page"] = related
        issues.append(item)

    for page, slide in enumerate(deck["slides"], 1):
        body = _body(slide)
        if any(_INSTRUCTIONS.search(text) for text in [slide["title"], *body]):
            issue(
                page,
                "instruction_echo",
                "Replace generation instructions with audience-facing content",
            )
        if (
            slide["layout"] == "bullets"
            and len(body) >= 2
            and all(_DISCLOSURE.search(text) for text in body)
        ):
            issue(
                page,
                "disclosure_only",
                "Move repeated disclosures to subtitle/footer/notes and give this page a distinct purpose",
            )
        if slide["layout"] in {"chart", "table"} and not slide.get("source"):
            issue(
                page, "missing_source", "Add a source or simulation disclosure to the evidence page"
            )

    bullet_pages = [(i, s) for i, s in enumerate(deck["slides"], 1) if s["layout"] == "bullets"]
    for index, (first_page, first) in enumerate(bullet_pages):
        a = [_normalized(x) for x in first["bullets"]]
        for second_page, second in bullet_pages[index + 1 :]:
            b = [_normalized(x) for x in second["bullets"]]
            matches = sum(any(SequenceMatcher(None, x, y).ratio() >= 0.88 for y in b) for x in a)
            duplicate = min(len(a), len(b)) >= 2 and matches / max(len(a), len(b)) >= 0.8
            first_numbers = set(re.findall(r"\d+(?:\.\d+)?", " ".join(first["bullets"])))
            second_numbers = set(re.findall(r"\d+(?:\.\d+)?", " ".join(second["bullets"])))
            repeated_summary = (
                _SUMMARY.search(first["title"])
                and _SUMMARY.search(second["title"])
                and len(first_numbers & second_numbers) >= 3
            )
            if duplicate or repeated_summary:
                issue(
                    second_page,
                    "duplicate_content",
                    "Give this page a distinct purpose rather than repeating an earlier summary",
                    first_page,
                )
    return {
        "status": "issues_found" if issues else "passed",
        "issues": issues,
        "scope": "instruction echoes, disclosure-only pages, repeated bullet pages and evidence sources",
        "factual_accuracy": "not_verified",
        "limitations": [
            "Heuristics may flag legitimate instructional/repeated content and miss paraphrases; editorial judgement remains necessary."
        ],
    }
