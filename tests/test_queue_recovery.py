import asyncio
import json

import pytest
from filelock import Timeout

from ppt_generate import DeckPipeline
from ppt_generate.core.tasks import GenerationQueue


def test_exclusive_queue_owner_and_export_recovery(tmp_path, monkeypatch):
    pipeline = DeckPipeline(tmp_path)
    deck = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "cover", "title": "Report"}],
    }
    exported = pipeline.render(deck)
    root = tmp_path / "tasks"
    root.mkdir()
    task_id = "a" * 32
    (root / f"{task_id}.json").write_text(
        json.dumps(
            {"task_id": task_id, "status": "exporting", "job_id": exported["job_id"], "request": {}}
        ),
        encoding="utf-8",
    )

    async def forbidden(*args, **kwargs):
        raise AssertionError("Recovered artifact must not repeat a model request")

    monkeypatch.setattr("ppt_generate.core.tasks.plan_deck", forbidden)

    async def scenario():
        first = GenerationQueue(pipeline)
        second = GenerationQueue(pipeline)
        try:
            result = await first.get(task_id)
            assert result["status"] == "completed"
            assert result["result"]["revision"] == exported["revision"]
            with pytest.raises(Timeout):
                await second.start()
        finally:
            await first.close()
            await second.close()

    asyncio.run(asyncio.wait_for(scenario(), 5))
