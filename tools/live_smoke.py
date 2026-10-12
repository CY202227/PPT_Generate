"""Explicit live API smoke test; uses only locally configured credentials."""

import asyncio
import json
import os
from pathlib import Path

from ppt_generate.core.errors import failure
from ppt_generate.core.pipeline import DeckPipeline, plan_deck


async def main():
    root = Path(__file__).resolve().parents[1]
    os.environ["PPT_GENERATE_ENV_FILE"] = str(root / ".env")
    source = (root / "examples/quarterly_source.md").read_text(encoding="utf-8")
    diagnostics = {}
    deck = await plan_deck(
        "示例企业季度经营汇报",
        8,
        "企业管理层",
        source,
        diagnostics=diagnostics,
    )
    pipeline = DeckPipeline()
    result = pipeline.render(deck, generation_report=diagnostics)
    result = pipeline.preview(result["job_id"], "powerpoint", result["revision"])
    (root / "outputs" / "live-smoke.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        result = failure(error)
        root = Path(__file__).resolve().parents[1]
        (root / "outputs").mkdir(exist_ok=True)
        (root / "outputs" / "live-smoke-failure.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(1) from None
