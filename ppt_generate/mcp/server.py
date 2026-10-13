"""MCP tools for editable presentations, using stdio for agent integration."""

import asyncio
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.tools.base import ToolResult
from fastmcp.utilities.types import Image as MCPImage

from ppt_generate.core.deck import get_schema
from ppt_generate.core.documents import extract_document
from ppt_generate.core.errors import failure
from ppt_generate.core.evidence import get_evidence_schema
from ppt_generate.core.pipeline import DeckPipeline, plan_deck
from ppt_generate.core.retention import cleanup_job
from ppt_generate.core.tasks import GenerationQueue


class PPTGenerateServer:
    def __init__(self, output_root=None):
        self.pipeline = DeckPipeline(output_root)
        self.tasks = GenerationQueue(self.pipeline)

        @asynccontextmanager
        async def lifespan(app):
            try:
                yield
            finally:
                await self.tasks.close()

        self.app = FastMCP("ppt-generate", lifespan=lifespan)
        self.preview_lock = asyncio.Lock()
        self._setup_tools()

    def _setup_tools(self):
        @self.app.tool()
        async def get_slide(
            job_id: str, page_number: int, base_revision: str | None = None
        ) -> dict:
            """Read one slide, resolved geometry and quality issues without a browser or Office.

            Use its revision for update_slide to avoid overwriting concurrent edits.
            """
            try:
                return await asyncio.to_thread(
                    self.pipeline.get_slide, job_id, page_number, base_revision
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def preview_slide(
            job_id: str, page_number: int, base_revision: str | None = None
        ) -> ToolResult:
            """Return a slide PNG directly to the model plus SVG/HTML and structured geometry.

            No browser control or Office installation needed. Requires preview extra.
            Native fonts/chart internals may differ from Office; human review remains required.
            """
            try:
                result = await asyncio.to_thread(
                    self.pipeline.preview_slide, job_id, page_number, base_revision
                )
                return ToolResult(
                    content=[MCPImage(path=result["preview_file"]), result],
                    structured_content=result,
                )
            except Exception as error:
                return ToolResult(structured_content=failure(error))

        @self.app.tool()
        async def update_slide(
            job_id: str, page_number: int, slide: dict, base_revision: str
        ) -> ToolResult:
            """Save one slide revision, export editable PPTX and return its Office-free preview.

            Only the selected slide changes; stale revisions are rejected. Exported PPTX
            is preserved if preview fails, with preview_error in the result.
            """
            result = None
            try:
                result = await asyncio.to_thread(
                    self.pipeline.revise, job_id, page_number, slide, base_revision
                )
                preview = await asyncio.to_thread(
                    self.pipeline.preview_slide, job_id, page_number, result["revision"]
                )
                preview["exported_file"] = result["exported_file"]
                return ToolResult(
                    content=[MCPImage(path=preview["preview_file"]), preview],
                    structured_content=preview,
                )
            except Exception as error:
                if result:
                    result["preview_error"] = failure(error)["error"]
                    return ToolResult(structured_content=result)
                return ToolResult(structured_content=failure(error))

        @self.app.tool()
        async def cleanup_history(
            job_id: str, keep: int = 3, older_than_days: int = 30, apply: bool = False
        ) -> dict:
            """Preview old revisions, terminal repairs and unused current snapshots for cleanup.

            Never removes current artifacts; keeps latest three revisions and 30 days.
            apply=true deletes selected history and requires the caller's explicit deletion intent.
            """
            try:
                return await asyncio.to_thread(
                    cleanup_job, self.pipeline, job_id, keep, older_than_days, apply
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def cleanup_tasks(
            keep: int = 20, older_than_days: int = 30, apply: bool = False
        ) -> dict:
            """Preview old terminal ticket cleanup; dry-run by default.

            Protects active tasks and exported PPTX jobs. apply=true requires explicit
            deletion intent. Removed ticket IDs become unavailable to get_task.
            """
            try:
                return await self.tasks.cleanup(keep, older_than_days, apply)
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def submit_ppt(
            topic: str,
            research_report: str,
            num_slides: int = 8,
            target_audience: str = "general",
            slide_count_mode: str = "adaptive",
        ) -> dict:
            """Queue generation and return a task ID immediately. Two planners, ten active tasks.

            Source is saved locally; credentials are not saved in tickets. Queued tickets
            resume on next queue access after restart; interrupted tasks require resubmission.
            """
            try:
                return await self.tasks.submit(
                    topic, research_report, num_slides, target_audience, slide_count_mode
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def get_task(task_id: str) -> dict:
            """Read queued/planning/exporting/completed/failed/cancelled/interrupted task state."""
            try:
                return await self.tasks.get(task_id)
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def cancel_task(task_id: str) -> dict:
            """Cancel queued/planning work. Atomic export cannot be cancelled safely.

            Does not abort PowerPoint previews or already-created presentations.
            """
            try:
                return await self.tasks.cancel(task_id)
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def create_ppt(
            topic: str,
            num_slides: int = 10,
            style: str = "formal",
            target_audience: str = "general",
            research_report: str = "",
            template_pptx_path: str | None = None,
            export_format: str = "pptx",
            slide_count_mode: str = "adaptive",
        ) -> dict:
            """Generate editable PPTX from source material. Requires LLM key and report.

            Supports formal native PPTX only. Returns paths and quality status.
            External templates are unsupported. Visual review remains required.
            """
            try:
                if style != "formal" or export_format != "pptx" or template_pptx_path:
                    raise ValueError("Supports formal PPTX only, without external templates")
                diagnostics = {}
                deck = await plan_deck(
                    topic,
                    num_slides,
                    target_audience,
                    research_report,
                    diagnostics=diagnostics,
                    slide_count_mode=slide_count_mode,
                )
                return await asyncio.to_thread(
                    self.pipeline.render,
                    deck,
                    generation_report=diagnostics,
                    source_material=research_report,
                )
            except Exception as error:
                return failure(error)

        @self.app.tool(name="render_deck")
        async def render(deck: dict, source_material: str | None = None) -> dict:
            """Render agent-authored JSON without a model or network.

            Requires schema_version=1.0, title, slides. Use get_deck_schema for details.
            Supports cover, bullets, split, table, chart, kpi, timeline. Output objects are editable.
            Optional source_material enables numeric checks and is saved as local job data.
            """
            try:
                return await asyncio.to_thread(
                    self.pipeline.render, deck, source_material=source_material
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def revise_slide(
            job_id: str, page_number: int, slide: dict, base_revision: str | None = None
        ) -> dict:
            """Replace a 1-based page in a saved job and export a new revision.

            Other page content is preserved. Old artifacts survive a failed revision.
            """
            try:
                return await asyncio.to_thread(
                    self.pipeline.revise, job_id, page_number, slide, base_revision
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def preview_ppt(
            job_id: str, backend: str = "auto", base_revision: str | None = None
        ) -> dict:
            """Render PNG pages and attach scoped layout evidence to a saved job.

            auto/native use Office-free previews (preview extra); powerpoint/libreoffice
            explicitly request those applications. Backend scopes differ; human review remains required.
            """
            try:
                async with self.preview_lock:
                    return await asyncio.to_thread(
                        self.pipeline.preview, job_id, backend, base_revision
                    )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def repair_ppt(
            job_id: str, base_revision: str | None = None, max_attempts: int = 2
        ) -> dict:
            """Repair native/PowerPoint overflow and conservative overlap/bounds without changing content.

            Requires a prior failing native or PowerPoint preview. At most two preview attempts;
            only a clean candidate is promoted. Unsupported defects retain the original.
            """
            try:
                return await asyncio.to_thread(
                    self.pipeline.repair_preview, job_id, base_revision, max_attempts
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def bind_evidence(job_id: str, bindings: list[dict], base_revision: str) -> dict:
            """Attach exact source quotes and offsets to chart value JSON paths.

            Use path/start/quote for literal evidence, or path/derivation for whitelisted
            source-backed decimal calculations. Get the evidence schema via get_deck_schema.
            Human semantic review remains required.
            """
            try:
                return await asyncio.to_thread(
                    self.pipeline.bind_evidence, job_id, bindings, base_revision
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def record_review(
            job_id: str, kind: str, decision: str, reviewer: str, base_revision: str, note: str = ""
        ) -> dict:
            """Record an explicitly supplied human factual_review or visual_review.

            Decisions: approved/rejected. Do not invent reviewer decisions or approve
            on behalf of a human. Known automated blockers cannot be overridden.
            This local record does not authenticate reviewer identity.
            """
            try:
                return await asyncio.to_thread(
                    self.pipeline.record_review,
                    job_id,
                    kind,
                    decision,
                    reviewer,
                    base_revision,
                    note,
                )
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def get_job(job_id: str) -> dict:
            """Retrieve latest manifest, deck and quality findings to resume or revise a job.

            Includes source/calculate proof checks without needing filesystem JSON access.
            """
            try:
                return await asyncio.to_thread(self.pipeline.get_job, job_id)
            except Exception as error:
                return failure(error)

        @self.app.tool()
        async def read_document(path: str) -> dict:
            """Read a trusted local Markdown, TXT, PDF or DOCX file into bounded source text.

            PDF/DOCX require the documents extra. No OCR or web fetching.
            This local server runs with the caller's filesystem privileges.
            """
            try:
                return {"success": True, **await asyncio.to_thread(extract_document, path)}
            except Exception as error:
                return failure(error)

        @self.app.tool()
        def get_deck_schema() -> dict:
            """Get interchange constraints for upstream agents. Every slide needs title."""
            return {
                "schema_version": "1.0",
                "json_schema": get_schema(),
                "evidence_binding_schema": get_evidence_schema(),
                "quality": "Dense content can be rejected; shorten or split it. Visual review required.",
            }

    def run(self):
        self.app.run(transport="stdio", show_banner=False)


def main():
    PPTGenerateServer().run()


if __name__ == "__main__":
    main()
