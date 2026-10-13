"""Offline source-backed growth calculation; human approval is deliberately pending."""

import argparse
import json
from pathlib import Path

from ppt_generate import DeckPipeline


def run(root, preview="none"):
    example = Path(__file__).resolve().parent
    deck = json.loads((example / "calculated_report.json").read_text(encoding="utf-8"))
    bindings = json.loads((example / "calculated_bindings.json").read_text(encoding="utf-8"))
    source = (example / "calculated_source.md").read_text(encoding="utf-8")
    pipeline = DeckPipeline(root)
    original = pipeline.render(deck, source_material=source)
    assert "evidence" in original["delivery"]["blocked_by"]
    result = pipeline.bind_evidence(original["job_id"], bindings, original["revision"])
    assert not result["delivery"]["blocked_by"]
    if preview != "none":
        result = pipeline.preview(result["job_id"], preview, result["revision"])
    assert not result["delivery"]["ready"]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("outputs/calculated-example"))
    parser.add_argument("--preview", choices=["none", "powerpoint", "libreoffice"], default="none")
    args = parser.parse_args()
    result = run(args.output_root, args.preview)
    print(json.dumps(result, indent=2))
