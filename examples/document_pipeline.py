"""Reproducible synthetic document -> evidence-bound editable deck, without a model.

Run: python examples/document_pipeline.py --format pdf --preview powerpoint
PDF/DOCX require the documents extra. Generated files live in outputs, not the package.
"""

import argparse
import json
import re
from pathlib import Path

from ppt_generate import DeckPipeline
from ppt_generate.core.documents import extract_document

SOURCE = """Synthetic operating report
2026 Q1 Revenue 100 CNY
2026 Q2 Revenue 125 CNY
2026 Q3 Revenue 150 CNY
Risk: customer concentration. Response: diversify customer acquisition.
Risk: delivery delays. Response: weekly delivery checkpoints.
Action: diversify acquisition. Owner: Sales. Deadline: Q4.
Action: improve delivery. Owner: Operations. Deadline: Q4.
"""


def run(root, format="md", preview="none"):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"source.{format}"
    if format == "md":
        path.write_text(SOURCE, encoding="utf-8")
    elif format == "docx":
        from docx import Document

        document = Document()
        for line in SOURCE.splitlines():
            document.add_paragraph(line)
        document.save(path)
    elif format == "pdf":
        import fitz

        with fitz.open() as document:
            page = document.new_page()
            page.insert_textbox(fitz.Rect(50, 50, 545, 750), SOURCE, fontsize=11)
            document.save(path)
    else:
        raise ValueError("format must be md, pdf or docx")
    source = extract_document(path)["text"]
    matches = list(re.finditer(r"2026 (Q[1-3]) Revenue (\d+) CNY", source))
    if len(matches) != 3:
        raise ValueError("Example extraction did not preserve the source rows")
    deck = {
        "schema_version": "1.0",
        "title": "Synthetic operating report",
        "slides": [
            {"layout": "cover", "title": "Operating report", "subtitle": "2026 — synthetic data"},
            {
                "layout": "bullets",
                "title": "Executive summary",
                "bullets": [
                    "Q3 revenue: 150 CNY",
                    "Concentration and delivery remain operating risks",
                    "Sales and Operations own the Q4 actions",
                ],
                "source": path.name,
            },
            {
                "layout": "chart",
                "title": "Revenue progression",
                "unit": "CNY",
                "period": "2026",
                "categories": [m[1] for m in matches],
                "series": [{"name": "Revenue", "values": [int(m[2]) for m in matches]}],
                "source": path.name,
            },
            {
                "layout": "split",
                "title": "Risks and responses",
                "columns": [
                    {
                        "heading": "Customer concentration",
                        "bullets": ["Diversify customer acquisition"],
                    },
                    {"heading": "Delivery delays", "bullets": ["Weekly delivery checkpoints"]},
                ],
                "source": path.name,
            },
            {
                "layout": "table",
                "title": "Q4 action plan",
                "headers": ["Action", "Owner", "Deadline"],
                "rows": [
                    ["Diversify acquisition", "Sales", "Q4"],
                    ["Improve delivery", "Operations", "Q4"],
                ],
                "source": path.name,
            },
        ],
    }
    pipeline = DeckPipeline(root / "jobs")
    result = pipeline.render(deck, source_material=source)
    bindings = [
        {"path": f"/slides/2/series/0/values/{index}", "start": match.start(), "quote": match[0]}
        for index, match in enumerate(matches)
    ]
    result = pipeline.bind_evidence(result["job_id"], bindings, result["revision"])
    if preview != "none":
        result = pipeline.preview(result["job_id"], preview, result["revision"])
    (root / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    # Human review is deliberately not fabricated by this example.
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["md", "pdf", "docx"], default="md")
    parser.add_argument("--preview", choices=["none", "powerpoint", "libreoffice"], default="none")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    result = run(
        args.output_root or Path("outputs/document-example") / args.format,
        args.format,
        args.preview,
    )
    print(json.dumps(result, indent=2))
