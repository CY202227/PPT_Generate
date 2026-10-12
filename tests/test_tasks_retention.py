import asyncio
import json
from pathlib import Path

import pytest

from ppt_generate import DeckPipeline
from ppt_generate.core.retention import cleanup_job
from ppt_generate.core.tasks import GenerationQueue

DECK = {
    "schema_version": "1.0",
    "title": "Report",
    "slides": [{"layout": "cover", "title": "Report"}],
}


def test_cancel_planning_and_queued_tasks_without_export(tmp_path, monkeypatch):
    async def scenario():
        started = asyncio.Event()

        async def plan(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr("ppt_generate.core.tasks.plan_deck", plan)
        queue = GenerationQueue(DeckPipeline(tmp_path), concurrency=1, capacity=2)
        try:
            one = await queue.submit("Report", "Private source")
            await started.wait()
            two = await queue.submit("Second", "Private source")
            with pytest.raises(ValueError, match="full"):
                await queue.submit("Third", "Private source")
            assert (await queue.cancel(two["task_id"]))["status"] == "cancelled"
            assert (await queue.cancel(one["task_id"]))["status"] == "cancelled"
            assert "Private" not in json.dumps(await queue.get(one["task_id"]))
            assert not list(tmp_path.rglob("presentation.pptx"))
        finally:
            await queue.close()

    asyncio.run(asyncio.wait_for(scenario(), 5))


def test_completed_result_and_restart_do_not_repeat_model(tmp_path, monkeypatch):
    calls = []

    async def plan(*args, **kwargs):
        calls.append(1)
        return DECK

    monkeypatch.setattr("ppt_generate.core.tasks.plan_deck", plan)

    async def scenario():
        queue = GenerationQueue(DeckPipeline(tmp_path))
        ticket = await queue.submit("Report", "Source")
        await queue.queue.join()
        status = await queue.get(ticket["task_id"])
        assert status["status"] == "completed"
        assert Path(status["result"]["exported_file"]).is_file()
        await queue.close()
        restarted = GenerationQueue(DeckPipeline(tmp_path))
        assert (await restarted.get(ticket["task_id"]))["status"] == "completed"
        await restarted.close()

    asyncio.run(asyncio.wait_for(scenario(), 5))
    assert len(calls) == 1


def test_interrupted_planning_is_not_replayed(tmp_path, monkeypatch):
    async def scenario():
        started = asyncio.Event()

        async def plan(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr("ppt_generate.core.tasks.plan_deck", plan)
        queue = GenerationQueue(DeckPipeline(tmp_path))
        ticket = await queue.submit("Report", "Source")
        await started.wait()
        await queue.close()
        restarted = GenerationQueue(DeckPipeline(tmp_path))
        assert (await restarted.get(ticket["task_id"]))["status"] == "interrupted"
        await restarted.close()

    asyncio.run(asyncio.wait_for(scenario(), 5))


def test_cleanup_dry_run_and_apply_keep_current(tmp_path):
    pipeline = DeckPipeline(tmp_path)
    first = pipeline.render(DECK)
    second = pipeline.revise(first["job_id"], 1, {"layout": "cover", "title": "Second"})
    before = (tmp_path / first["job_id"] / "manifest.json").read_bytes()
    dry = cleanup_job(pipeline, first["job_id"], keep=1, older_than_days=0)
    assert dry["dry_run"] and len(dry["selected"]) == 1
    assert Path(first["exported_file"]).is_file()
    cleanup_job(pipeline, first["job_id"], keep=1, older_than_days=0, apply=True)
    assert not Path(first["exported_file"]).exists()
    assert Path(second["exported_file"]).is_file()
    assert (tmp_path / first["job_id"] / "manifest.json").read_bytes() == before


def test_export_cannot_be_cancelled_and_shutdown_waits(tmp_path, monkeypatch):
    import threading

    started, release = threading.Event(), threading.Event()
    pipeline = DeckPipeline(tmp_path)
    render = pipeline.render

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return render(*args, **kwargs)

    monkeypatch.setattr(pipeline, "render", slow)

    async def plan(*args, **kwargs):
        return DECK

    monkeypatch.setattr("ppt_generate.core.tasks.plan_deck", plan)

    async def scenario():
        queue = GenerationQueue(pipeline)
        ticket = await queue.submit("Report", "Source")
        try:
            assert await asyncio.to_thread(started.wait, 3)
            result = await queue.cancel(ticket["task_id"])
            assert result["error"]["code"] == "not_cancellable"
            closing = asyncio.create_task(queue.close())
            await asyncio.sleep(0)
            assert not closing.done()
            release.set()
            await closing
            assert queue.records[ticket["task_id"]]["status"] == "completed"
        finally:
            release.set()
            await queue.close()

    asyncio.run(asyncio.wait_for(scenario(), 5))
