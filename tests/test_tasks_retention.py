import asyncio
import json
import os
import subprocess
import time
from datetime import datetime, timezone
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


def test_snapshot_cleanup_protects_references_recent_files_and_latest(tmp_path):
    pipeline = DeckPipeline(tmp_path)
    result = pipeline.render(DECK)
    revision = tmp_path / result["job_id"] / result["revision"]
    old = time.time() - 40 * 86400
    quality = Path(result["quality_report"]).read_bytes()
    snapshots = {}
    for kind in ("previews", "reviews"):
        snapshots[kind] = []
        for index in range(5):
            directory = revision / kind / f"{index:032x}"
            directory.mkdir(parents=True)
            file = directory / "quality.json"
            file.write_bytes(quality)
            os.utime(file, (old, old) if index != 2 else (time.time(), time.time()))
            os.utime(directory, (old + index, old + index))
            snapshots[kind].append(directory)
    manifest = tmp_path / result["job_id"] / "manifest.json"
    result["preview_report"] = str(snapshots["previews"][0] / "quality.json")
    result["quality_report"] = str(snapshots["reviews"][0] / "quality.json")
    manifest.write_text(json.dumps(result), encoding="utf-8")
    before = manifest.read_bytes()
    selected = cleanup_job(pipeline, result["job_id"], keep=1)
    assert len(selected["selected"]) == 4
    assert all(directory.exists() for group in snapshots.values() for directory in group)
    cleanup_job(pipeline, result["job_id"], keep=1, apply=True)
    for group in snapshots.values():
        assert all(group[index].exists() for index in (0, 2, 4))
        assert all(not group[index].exists() for index in (1, 3))
    assert manifest.read_bytes() == before
    assert Path(result["exported_file"]).is_file()


def test_terminal_task_cleanup_preserves_jobs_active_tasks_and_worker(tmp_path):
    async def scenario():
        pipeline = DeckPipeline(tmp_path)
        job = pipeline.render(DECK)
        queue = GenerationQueue(pipeline, concurrency=1)
        await queue.start()
        old = time.time() - 40 * 86400
        statuses = ["completed", "failed", "cancelled", "interrupted", "completed", "queued"]
        try:
            for index, status in enumerate(statuses):
                task_id = f"{index:032x}"
                record = {
                    "task_id": task_id,
                    "status": status,
                    "updated_at": datetime.fromtimestamp(old + index, timezone.utc).isoformat(),
                }
                if status == "completed":
                    record["result"] = job
                queue.records[task_id] = record
                path = queue.root / (task_id + ".json")
                path.write_text(json.dumps(record), encoding="utf-8")
                os.utime(path, (old, old))
            # Cancelled queued tickets can still be in the worker's queue when cleaned.
            queue.queue.put_nowait(f"{2:032x}")
            dry = await queue.cleanup(keep=1)
            assert len(dry["selected"]) == 4
            assert len(queue.records) == 6
            applied = await queue.cleanup(keep=1, apply=True)
            assert applied["bytes"] == dry["bytes"]
            assert set(queue.records) == {f"{4:032x}", f"{5:032x}"}
            await asyncio.wait_for(queue.queue.join(), 2)
            assert not queue.workers[0].done()
            with pytest.raises(FileNotFoundError):
                await queue.get(f"{2:032x}")
            assert Path(job["exported_file"]).is_file()
        finally:
            await queue.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("options", [{"keep": True}, {"older_than_days": -1}, {"apply": "yes"}])
def test_task_cleanup_rejects_invalid_policy_before_start(tmp_path, options):
    queue = GenerationQueue(DeckPipeline(tmp_path))
    with pytest.raises(ValueError):
        asyncio.run(queue.cleanup(**options))
    assert not queue.root.exists()


@pytest.mark.parametrize("subject", ["snapshots", "tasks"])
def test_cleanup_refuses_real_directory_links(tmp_path, subject):
    pipeline = DeckPipeline(tmp_path / "outputs")
    result = pipeline.render(DECK)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("must remain", encoding="utf-8")
    target = (
        pipeline.root / result["job_id"] / result["revision"] / "previews"
        if subject == "snapshots"
        else pipeline.root / "tasks"
    )
    if os.name == "nt":
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(outside)],
            capture_output=True,
            check=False,
        )
        assert created.returncode == 0
    else:
        target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="linked"):
        if subject == "snapshots":
            cleanup_job(pipeline, result["job_id"], keep=1, older_than_days=0, apply=True)
        else:
            asyncio.run(GenerationQueue(pipeline).cleanup(apply=True))
    assert sentinel.read_text(encoding="utf-8") == "must remain"
    assert Path(result["exported_file"]).is_file()
