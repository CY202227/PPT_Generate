"""Bounded persisted generation queue; safe cancellation before atomic export."""

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone

from filelock import FileLock

from .errors import failure
from .pipeline import plan_deck


class GenerationQueue:
    def __init__(self, pipeline, concurrency=2, capacity=10):
        self.pipeline = pipeline
        self.root = pipeline.root / "tasks"
        self.concurrency, self.capacity = concurrency, capacity
        self.records, self.running = {}, {}
        self.queue = asyncio.Queue()
        self.workers = []
        self.stopping = False
        self.owner_lock = FileLock(self.root / ".queue.lock", timeout=0)

    def _write(self, record):
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        pending = self.root / (record["task_id"] + ".tmp")
        pending.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        pending.replace(self.root / (record["task_id"] + ".json"))

    async def start(self):
        if self.workers:
            return
        self.stopping = False
        self.queue = asyncio.Queue()
        self.root.mkdir(parents=True, exist_ok=True)
        self.owner_lock.acquire()
        try:
            for path in self.root.glob("*.json"):
                if not re.fullmatch(r"[0-9a-f]{32}", path.stem):
                    continue
                record = json.loads(path.read_text(encoding="utf-8"))
                if record.get("task_id") != path.stem:
                    raise ValueError("Invalid saved task")
                if record["status"] in {"planning", "exporting"}:
                    record["status"] = "interrupted"
                    if record.get("job_id"):
                        try:
                            record["result"] = self.pipeline.get_job(record["job_id"])["manifest"]
                            record["status"] = "completed"
                        except (FileNotFoundError, ValueError):
                            pass
                    self._write(record)
                self.records[path.stem] = record
                if record["status"] == "queued":
                    self.queue.put_nowait(path.stem)
        except BaseException:
            self.owner_lock.release()
            self.records.clear()
            raise
        self.workers = [asyncio.create_task(self._worker()) for _ in range(self.concurrency)]

    async def submit(
        self, topic, report, slides=8, audience="general", slide_count_mode="adaptive"
    ):
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 200:
            raise ValueError("topic must be nonempty text up to 200 characters")
        if not isinstance(report, str) or not report.strip() or len(report) > 100_000:
            raise ValueError("report must be nonempty text up to 100,000 characters")
        if isinstance(slides, bool) or not isinstance(slides, int) or not 1 <= slides <= 40:
            raise ValueError("slides must be 1–40")
        if slide_count_mode not in {"exact", "adaptive"}:
            raise ValueError("slide_count_mode must be exact or adaptive")
        if not isinstance(audience, str) or not audience.strip() or len(audience) > 200:
            raise ValueError("audience must be bounded text")
        await self.start()
        if (
            sum(r["status"] in {"queued", "planning", "exporting"} for r in self.records.values())
            >= self.capacity
        ):
            raise ValueError("Generation queue is full; retry after a task finishes")
        task_id = uuid.uuid4().hex
        record = {
            "task_id": task_id,
            "status": "queued",
            "request": {
                "topic": topic,
                "report": report,
                "slides": slides,
                "audience": audience,
                "slide_count_mode": slide_count_mode,
            },
        }
        self.records[task_id] = record
        self._write(record)
        self.queue.put_nowait(task_id)
        return self._public(record)

    def _public(self, record):
        return {
            "success": True,
            **{key: value for key, value in record.items() if key != "request"},
        }

    async def get(self, task_id):
        await self.start()
        if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{32}", task_id):
            raise ValueError("invalid task_id")
        if task_id not in self.records:
            raise FileNotFoundError("Task does not exist")
        return self._public(self.records[task_id])

    async def cancel(self, task_id):
        await self.get(task_id)
        record = self.records[task_id]
        if record["status"] == "queued":
            record["status"] = "cancelled"
            self._write(record)
        elif record["status"] == "planning":
            record["cancellation_requested"] = True
            self.running[task_id].cancel()
            await asyncio.gather(self.running[task_id], return_exceptions=True)
        elif record["status"] == "exporting":
            return {
                "success": False,
                "error": {
                    "code": "not_cancellable",
                    "message": "Atomic export has started; wait for the result",
                },
                "task_id": task_id,
            }
        return self._public(record)

    async def _execute(self, record):
        request = record["request"]
        diagnostics = {}
        try:
            record["status"] = "planning"
            self._write(record)
            deck = await plan_deck(
                request["topic"],
                request["slides"],
                request["audience"],
                request["report"],
                diagnostics=diagnostics,
                slide_count_mode=request["slide_count_mode"],
            )
            record["status"] = "exporting"
            record["job_id"] = uuid.uuid4().hex
            self._write(record)
            record["result"] = await asyncio.to_thread(
                self.pipeline.render,
                deck,
                job_id=record["job_id"],
                generation_report=diagnostics,
                source_material=request["report"],
            )
            record["status"] = "completed"
        except asyncio.CancelledError:
            record["status"] = (
                "cancelled" if record.get("cancellation_requested") else "interrupted"
            )
            raise
        except Exception as error:
            record["status"] = "failed"
            record["error"] = failure(error)["error"]
            record["diagnostics"] = diagnostics
        finally:
            self._write(record)

    async def _worker(self):
        while True:
            task_id = await self.queue.get()
            try:
                record = self.records[task_id]
                if self.stopping or record["status"] != "queued":
                    continue
                task = asyncio.create_task(self._execute(record))
                self.running[task_id] = task
                await asyncio.gather(task, return_exceptions=True)
            finally:
                self.running.pop(task_id, None)
                self.queue.task_done()

    async def close(self):
        self.stopping = True
        # Finish exports; stop planning without presenting shutdown as user cancellation.
        for task_id, task in list(self.running.items()):
            if self.records[task_id]["status"] == "exporting":
                await asyncio.shield(task)
            else:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self.records[task_id]["status"] = "interrupted"
                self._write(self.records[task_id])
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []
        self.owner_lock.release()
