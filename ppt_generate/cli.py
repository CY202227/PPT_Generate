"""Installed CLI for validation, rendering, ingestion and generation."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from . import __version__
from .core.deck import get_schema, validate_deck
from .core.documents import extract_document
from .core.errors import failure
from .core.pipeline import DeckPipeline, plan_deck
from .core.retention import cleanup_job


def main():
    parser = argparse.ArgumentParser(prog="ppt-generate")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["render", "validate"]:
        p = commands.add_parser(name)
        p.add_argument("deck", type=Path)
        if name == "render":
            p.add_argument("--output-root", type=Path)
            p.add_argument("--source", type=Path)
            p.add_argument(
                "--preview-backend",
                choices=["none", "auto", "powerpoint", "libreoffice"],
                default="none",
            )
    commands.add_parser("schema")
    p = commands.add_parser("extract")
    p.add_argument("document", type=Path)
    p = commands.add_parser("generate")
    p.add_argument("--topic", required=True)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--slides", type=int, default=8)
    p.add_argument("--slide-count-mode", choices=["exact", "adaptive"], default="adaptive")
    p.add_argument("--audience", default="general")
    p.add_argument("--env-file", type=Path)
    p.add_argument("--output-root", type=Path)
    p.add_argument(
        "--preview-backend", choices=["none", "auto", "powerpoint", "libreoffice"], default="none"
    )
    p = commands.add_parser("preview")
    p.add_argument("job_id")
    p.add_argument("--backend", choices=["auto", "powerpoint", "libreoffice"], default="auto")
    p.add_argument("--base-revision")
    p.add_argument("--output-root", type=Path)
    p = commands.add_parser("job")
    p.add_argument("job_id")
    p.add_argument("--output-root", type=Path)
    p = commands.add_parser("repair")
    p.add_argument("job_id")
    p.add_argument("--base-revision")
    p.add_argument("--max-attempts", type=int, choices=[1, 2], default=2)
    p.add_argument("--output-root", type=Path)
    p = commands.add_parser("revise")
    p.add_argument("job_id")
    p.add_argument("page", type=int)
    p.add_argument("slide", type=Path)
    p.add_argument("--base-revision")
    p.add_argument("--output-root", type=Path)
    p = commands.add_parser("bind-evidence")
    p.add_argument("job_id")
    p.add_argument("bindings", type=Path)
    p.add_argument("--base-revision", required=True)
    p.add_argument("--output-root", type=Path)
    p = commands.add_parser("review")
    p.add_argument("job_id")
    p.add_argument("--kind", required=True, choices=["factual_review", "visual_review"])
    p.add_argument("--decision", required=True, choices=["approved", "rejected"])
    p.add_argument("--reviewer", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--base-revision", required=True)
    p.add_argument("--output-root", type=Path)
    p = commands.add_parser("cleanup")
    p.add_argument("job_id")
    p.add_argument("--keep", type=int, default=3)
    p.add_argument("--older-than-days", type=int, default=30)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "schema":
            result = get_schema()
        elif args.command == "extract":
            result = extract_document(args.document)
        elif args.command in {"render", "validate"}:
            deck = validate_deck(json.loads(args.deck.read_text(encoding="utf-8-sig")))
            result = (
                DeckPipeline(args.output_root).render(
                    deck,
                    source_material=extract_document(args.source)["text"] if args.source else None,
                )
                if args.command == "render"
                else {"success": True, "slide_count": len(deck["slides"])}
            )
            if args.command == "render" and args.preview_backend != "none":
                result = DeckPipeline(args.output_root).preview(
                    result["job_id"], args.preview_backend, result["revision"]
                )
        elif args.command == "generate":
            if args.env_file:
                os.environ["PPT_GENERATE_ENV_FILE"] = str(args.env_file.resolve())
            source = extract_document(args.report)
            report = f"SOURCE: {source['source']}\n{source['text']}"
            diagnostics = {}
            deck = asyncio.run(
                plan_deck(
                    args.topic,
                    args.slides,
                    args.audience,
                    report,
                    diagnostics=diagnostics,
                    slide_count_mode=args.slide_count_mode,
                )
            )
            pipeline = DeckPipeline(args.output_root)
            result = pipeline.render(deck, generation_report=diagnostics, source_material=report)
            if args.preview_backend != "none":
                result = pipeline.preview(
                    result["job_id"], args.preview_backend, result["revision"]
                )
        elif args.command == "preview":
            result = DeckPipeline(args.output_root).preview(
                args.job_id, args.backend, args.base_revision
            )
        elif args.command == "job":
            result = DeckPipeline(args.output_root).get_job(args.job_id)
        elif args.command == "repair":
            result = DeckPipeline(args.output_root).repair_preview(
                args.job_id, args.base_revision, args.max_attempts
            )
        elif args.command == "bind-evidence":
            result = DeckPipeline(args.output_root).bind_evidence(
                args.job_id,
                json.loads(args.bindings.read_text(encoding="utf-8-sig")),
                args.base_revision,
            )
        elif args.command == "review":
            result = DeckPipeline(args.output_root).record_review(
                args.job_id, args.kind, args.decision, args.reviewer, args.base_revision, args.note
            )
        elif args.command == "cleanup":
            result = cleanup_job(
                DeckPipeline(args.output_root),
                args.job_id,
                args.keep,
                args.older_than_days,
                args.apply,
            )
        else:
            slide = json.loads(args.slide.read_text(encoding="utf-8-sig"))
            result = DeckPipeline(args.output_root).revise(
                args.job_id, args.page, slide, args.base_revision
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        if (
            "result" in locals()
            and isinstance(result, dict)
            and result.get("exported_file")
            and args.command in {"render", "generate"}
        ):
            result["preview_error"] = failure(error)["error"]
            print(json.dumps(result, ensure_ascii=False, indent=2))
            raise SystemExit(2) from None
        print(json.dumps(failure(error), ensure_ascii=False))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
