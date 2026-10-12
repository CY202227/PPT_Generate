"""Opt-in real-provider test of agent queue; uses explicitly configured local credentials."""

import asyncio
import json
from pathlib import Path

from ppt_generate import DeckPipeline
from ppt_generate.core.tasks import GenerationQueue


async def run():
    root = Path("outputs/queue-smoke").resolve()
    queue = GenerationQueue(DeckPipeline(root))
    source = (
        "Synthetic report. In 2026, Q1 Revenue was 100 CNY and Q2 Revenue was 125 CNY. "
        "Q2 growth was 25%. Sales owner Chen will diversify acquisition in Q3."
    )
    try:
        ticket = await queue.submit("Synthetic operating update", source, 8, "management")
        print(json.dumps({"task_id": ticket["task_id"], "status": "queued"}), flush=True)
        await asyncio.wait_for(queue.queue.join(), timeout=650)
        status = await queue.get(ticket["task_id"])
        assert status["status"] == "completed", status.get("error")
        result = status["result"]
        assert 1 <= result["slide_count"] <= 8
        result = queue.pipeline.preview(result["job_id"], "powerpoint", result["revision"])
        (root / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": "completed",
                    "slides": result["slide_count"],
                    "layout_review": result["layout_review"],
                    "result_file": str(root / "result.json"),
                }
            ),
            flush=True,
        )
    finally:
        await queue.close()


if __name__ == "__main__":
    asyncio.run(run())
