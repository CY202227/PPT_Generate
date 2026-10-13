# PPT Generate

Editable enterprise PowerPoint generation for agent workflows.

**Status: 0.5.0 alpha, unreleased.** This project provides a reusable local pipeline for agent-authored and model-planned decks. It creates native editable text, tables and charts, supports Office-free previews through MCP, and keeps explicit human visual and factual review before a job can be marked ready. It does not claim enterprise design quality.

[中文说明](docs/README.zh-CN.md) · [Architecture](docs/architecture.md) · [Release gates](docs/roadmap.md)

## Quick start without an API key

Python 3.10+ is required. Create and activate a virtual environment, then install from a checkout:

```sh
python -m pip install .
ppt-generate validate examples/quarterly_report.json
ppt-generate render examples/quarterly_report.json --output-root outputs
```

The sample uses disclosed simulated figures. The command prints a job identifier, revision, PPTX path, deck JSON path and quality-report path. Each run creates a separate job. The installed package works outside the repository; supply an input path and an output directory.

No Office installation, model provider or network is required for rendering. The default CJK font is Microsoft YaHei; actual appearance depends on installed fonts. Review the rendered deck on your target presentation system.

## Optional capabilities

```sh
python -m pip install ".[llm,mcp,documents]"
```

- `llm`: plan slides from source material using an OpenAI-compatible chat completion endpoint.
- `mcp`: expose a trusted local stdio server to another agent.
- `documents`: extract text from PDFs and DOCX files. Markdown/TXT need no extra.

```sh
ppt-generate extract path/to/report.pdf
ppt-generate generate --topic "Quarterly operating report" --report examples/quarterly_source.md --slides 8 --env-file .env --output-root outputs
ppt-generate schema
```

Set `API_KEY`, `API_BASE_URL` and `MODEL_NAME` through environment variables or a private dotenv file. `LLM_API_KEY`, `LLM_BASE_URL` and `LLM_MODEL_NAME` take precedence. OpenAI environment aliases are also supported. Dotenv loading is explicit: use `--env-file` or `PPT_GENERATE_ENV_FILE`. Credentials are never bundled in distributions.

Generation sends supplied material to your configured provider. It requires evidence and checks page count, schema, capacity and editorial issues; it may request up to two corrected responses. A planning report records attempts and token usage. It does not guarantee that every model statement is factually correct.

## Agent integration

Install the MCP extra and configure an absolute executable path appropriate to your environment. The MCP extra includes the Office-free preview dependency so agents receive preview images without a separate extra:

```json
{
  "mcpServers": {
    "ppt-generate": {
      "command": "/absolute/path/to/venv/bin/ppt-generate-mcp",
      "env": {
        "PPT_GENERATE_OUTPUT_ROOT": "/absolute/path/to/jobs",
        "PPT_GENERATE_ENV_FILE": "/absolute/path/to/private.env"
      }
    }
  }
}
```

On Windows, the executable is `venv/Scripts/ppt-generate-mcp.exe`. Omit the dotenv setting if the upstream agent supplies all slide content and does not need model planning.

The eighteen tools support this loop: render agent-authored JSON or ask the model to draft a deck, read the latest job, inspect a slide image, update that slide with its revision token, then export the revised editable PPTX. `preview_slide` returns an MCP image so the agent client does not need browser control. Human reviewers can open the returned HTML gallery.

The eighteen tools are:

- `get_slide`: read one page, its geometry and current layout issues.
- `preview_slide`: return a PNG directly through MCP, plus SVG and an HTML gallery.
- `update_slide`: revise one page with version protection, export PPTX and return its preview.

- `get_deck_schema`: return the bundled JSON Schema 1.0.
- `read_document`: extract bounded text from a trusted local file.
- `submit_ppt`: submit a bounded background generation task; returns a task ID.
- `get_task`: inspect persisted state and retrieve completed artifact paths.
- `cancel_task`: cancel queued/planning work; atomic export is explicitly not cancellable.
- `cleanup_history`: dry-run old revisions, terminal candidates and unreferenced current preview/review snapshots; explicit apply deletes selected history.
- `cleanup_tasks`: dry-run old terminal task tickets; explicit apply deletes tickets while retaining exported jobs and active tasks.
- `create_ppt`: plan and render a formal PPTX from a topic, source report and requested page count.
- `render_deck`: render agent-authored slide JSON without a model call.
- `get_job`: load the latest manifest and deck for a saved job.
- `revise_slide`: replace one 1-based page and publish a new revision. Optional `base_revision` rejects stale edits.
- `bind_evidence`: attach exact source locations and quotes to chart values; checks contextual terminology and values.
- `record_review`: record explicit human factual/visual decisions for the current revision; automatic blockers cannot be overridden.
- `repair_ppt`: repair native/PowerPoint text overflow, conservative overlap and object bounds in isolated candidates, without changing content. At most two attempts; only a candidate with clean checks and no known quality blockers is promoted.
- `preview_ppt`: export PNG pages and attach version-bound layout evidence. Defaults to native; external rendering engines are optional.

Tool failures return `success: false` with `error.code` and `error.message`. Codes include `invalid_input`, `not_found`, `conflict`, `authentication`, `provider_unavailable`, `job_busy` and `internal_error`. A successful export indicates an artifact was generated, not that it passed visual review.

## Python API

```python
import json
from pathlib import Path
from ppt_generate import DeckPipeline

pipeline = DeckPipeline("outputs")
deck = json.loads(Path("examples/quarterly_report.json").read_text(encoding="utf-8"))
result = pipeline.render(deck)
saved = pipeline.get_job(result["job_id"])
slide = {"layout": "cover", "title": "Updated quarterly report"}
updated = pipeline.revise(result["job_id"], 1, slide, base_revision=result["revision"])
```

## Supported layouts and limits

Cover, bullets, two-column comparison, table, column chart and line chart. The contract permits 1–40 slides and bounded text/row/series counts. Table widths and chart data lengths are checked; unknown fields are rejected so content cannot be silently discarded. The bundled schema is the machine-readable reference.

Overflow uses conservative text-width estimates. Dense pages fail rather than silently shrinking text. Sources and speaker notes are retained. Data objects are native PowerPoint objects rather than whole-slide screenshots.

## Preview and verification

On Windows with PowerPoint installed:

```powershell
./tools/render_preview.ps1 -PptxPath '<exported_file>'
```

The script above is a legacy preview convenience. The installed, version-bound workflow is:

```sh
ppt-generate preview JOB_ID --backend powerpoint --output-root outputs
# Or Linux/macOS with LibreOffice on PATH:
python -m pip install ".[preview]"
ppt-generate preview JOB_ID --backend libreoffice --output-root outputs
```

`render` and `generate` also accept `--preview-backend`. `auto` selects the Office-independent `native` backend. Install `pip install -e ".[preview]"` for PNG previews in the local Python API or CLI; the MCP extra already includes it. Native preview reads exported PPTX geometry and produces SVG, PNG and an offline HTML gallery; fonts and chart internals can differ from Office. PowerPoint and LibreOffice remain explicit optional backends. Reports keep `visual_review: required`; known Office issues remain blockers after native preview. See the [sample gallery](docs/gallery/index.md).

Agents do not need browser control: call `get_slide(job_id, page_number)` to read page content and geometry, `preview_slide` to receive an inline PNG, then `update_slide(job_id, page_number, slide, base_revision)` to save a page and receive a new editable PPTX and preview. Use the returned revision as `base_revision`; stale edits are rejected. Image-capable MCP clients can inspect the PNG directly; text clients receive structured geometry. The HTML gallery is read-only; an interactive browser editor is not yet implemented. A preview failure after an edit preserves the exported revision and returns `preview_error`.

Tests cover native chart/table values, page revision preservation, failed-publication rollback, conflicting and concurrent edits, malformed contracts, document extraction, model repair mocks, installed CLI and stdio MCP startup. CI is configured for Linux/Windows and Python 3.10/3.12; actual remote CI results should be checked before a release.

See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and release builds. Wheel verification runs without a source checkout or LLM/MCP extras.

## Limitations

- Layout checks have backend-specific limits; automatic repair handles measured PowerPoint text overflow and conservative object repositioning. Oversized objects, crowded pages, chart labels and aesthetic certification remain unsupported.
- External template preservation, SmartArt, automatic illustration generation and HTML/PDF export are unsupported.
- PDF extraction does not perform OCR. Document parsing limits are documented in [SECURITY.md](SECURITY.md).
- Planning has a total deadline and records token usage when the provider supplies it; monetary cost reporting and scheduled automatic cleanup are not implemented. The bounded MCP queue and explicit dry-run-first history cleanup are available.
- The local MCP server is intended for trusted agents, not untrusted multi-user access.

The Microsoft financial-report reference is documented under `benchmarks/`; its third-party PPTX/images are local reference material and are excluded from release artifacts. `legacy/` preserves the older template/Marp implementation and is excluded from the supported package. Migration details are in [CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

### Bounded overflow repair

After a PowerPoint preview reports text overflow:

```sh
ppt-generate repair JOB_ID --base-revision REVISION --max-attempts 2 --output-root outputs
```

This changes font sizes in flagged text frames and conservatively repositions flagged overlapping/out-of-bounds objects, with a 24 pt top-of-slide and 18 pt body floor. Wording and values are preserved. The candidate is previewed before promotion; unsupported defects, failed previews and concurrent edits preserve the original manifest. Candidate artifacts and repair diagnostics are kept under the job's repair-candidates directory; accepted revision paths are returned in the normal manifest. A later JSON content revision regenerates standard styling, so preview it again. No model request or network is needed for this repair. Human visual and factual review remains required.

## Source evidence and explicit review

Seven native layouts are supported: cover, bullets, split, table, chart, kpi (1–3 metrics) and timeline (1–4 events). Schema 1.0 is extended additively in this alpha; use the bundled schema rather than hard-coded layout lists.

`render --source REPORT` saves extracted source material. `bind-evidence JOB_ID bindings.json --base-revision REVISION` attaches chart references. Each reference has a chart value JSON `path`, zero-based character `start` in saved source.txt, and exact `quote`. Metric, category, unit, period and value must occur in that quote; translation and semantic relationships are not automatically certified. Whitelisted derived values can use explicit calculation evidence. Missing chart bindings keep delivery pending. String claims and metric relationships still need human review.

`review JOB_ID --kind factual_review --decision approved --reviewer NAME --base-revision REVISION` records an explicitly supplied human decision. Use visual_review after inspecting engine previews. Rejection blocks delivery. Both approvals plus all required automated checks can make delivery.ready true. This local record does not authenticate identity. Never manufacture approvals. Changed content resets reviews/bindings; fresh previews reset visual approval, and new evidence bindings reset factual approval.

The offline [document pipeline example](examples/document_pipeline.py) creates synthetic PDF/DOCX/Markdown source, extracts it, renders five editable slides and binds each chart value to an exact source quote. Run:

```sh
python examples/document_pipeline.py --format pdf --preview powerpoint
python examples/document_pipeline.py --format docx --preview powerpoint
```

Install the documents extra for PDF/DOCX. Omit preview on systems without an engine. Results are saved under outputs/document-example. These reproducible examples make no model request and deliberately do not fabricate human review.

## Everyday use: page budgets, tasks and retention

CLI generation and MCP create_ppt/submit_ppt default to adaptive slide counts: the requested count is a maximum. Sparse source material may produce fewer pages rather than filler. Use --slide-count-mode exact (or slide_count_mode=exact) when an exact count is required. Direct Python plan_deck retains its exact-count default for compatibility. Planning records requested/actual counts; this is still model judgement, not a proof of content completeness.

submit_ppt returns a task_id immediately. get_task reports queued, planning, exporting, completed, failed, cancelled or interrupted. Two planners process at most ten active tickets. Source requests are saved locally under outputs/tasks; API credentials are not in tickets, and public status omits the request text. Only one queue owner may use an output root at a time. Queued tickets resume on the next queue access; interrupted planning is never silently replayed. Completed exports can be recovered from their saved job IDs after restart. Resubmit interrupted planning explicitly if wanted. cancel_task cancels queued or planning work; once atomic export starts it returns not_cancellable. It does not kill PowerPoint or remove completed files. The MCP server waits for exports during orderly shutdown.

```sh
ppt-generate cleanup JOB_ID --output-root outputs
# Inspect selected paths first; the following is an explicit deletion request:
ppt-generate cleanup JOB_ID --keep 3 --older-than-days 30 --apply --output-root outputs
```

Cleanup keeps the current revision and manifest-referenced artifacts, recent revisions and active repair candidates. Current preview/review snapshots use the same `keep` and age thresholds independently per category. A recent file inside an old snapshot protects the whole snapshot. Previews with retained Office evidence are conservatively kept. Linked trees, including Windows junctions, are rejected. By default cleanup lists candidates without deleting.

MCP `cleanup_tasks(keep=20, older_than_days=30, apply=false)` lists old completed, failed, cancelled or interrupted tickets. `apply=true` removes selected tickets and their saved source requests; their IDs become unavailable to `get_task`. Exported jobs and all queued/planning/exporting tasks are retained. These are explicit cleanup policies; scheduled automatic deletion is not implemented.

PowerPoint and LibreOffice run in an isolated process group. When the render timeout expires or the runner is interrupted, the tool stops that process group before releasing the renderer lock and discards the incomplete preview staging directory. A separately started PowerPoint COM server may still need manual inspection if Office itself hangs. External previews are synchronous; queue cancellation applies to planning work, not an active renderer call.

The foundation commit was checked on GitHub Actions under Windows/Linux and Python 3.10/3.12. This verifies core/tests/build/install across those runners, not Office/LibreOffice rendering there.

## MCP version and startup

The supported MCP dependency is FastMCP >=4.1,<5, tested with 4.1.0 and MCP SDK 2.3.0. Startup logs show the installed version and that the stdio service is waiting for agent requests. Advertising/update banners are disabled; runtime warnings and errors are not filtered out.

start_demo.py starts the MCP service and waits for an agent client. It does not automatically generate a deck. Restart an already-running process after upgrading. Use the CLI generation/rendering commands or the offline document example to make a presentation.

When migrating an existing v2 environment, pip can remove overlapping implementation files during uninstall. If import fails after upgrade, reinstall the implementation package matching the installed FastMCP version. The local 2.14.7 -> 4.1.0 migration was repaired with python -m pip install --force-reinstall --no-deps "fastmcp-slim[client,server]==4.1.0". Fresh installations used in CI do not need this repair step.

## Source-backed calculations

Evidence bindings support both literal path/start/quote and calculated path/derivation forms. The get_deck_schema MCP tool returns evidence_binding_schema for upstream agents. Calculated input quotes must contain the chart series metric and each input category, unit and period. Input periods must be represented in the output period (for example 2025–2026). Inputs must have one consistent unit; unit conversion and metric aliases/translations are not performed.

Operations use ordered inputs:

- sum: add 2–8 inputs; output uses the input unit.
- difference: first minus second; output uses the input unit.
- ratio: first divided by second; output unit is ratio.
- percentage: first divided by second times 100; output unit is %.
- percentage_change: (second minus first) divided by first times 100; output unit is %.

precision specifies 0–6 decimal places using decimal ROUND_HALF_UP. All operands need exact source offsets/quotes, and the displayed chart value must equal the rounded result. Duplicate operands, mismatched context/units, zero denominators and wrong answers block delivery. No arbitrary expressions or code are evaluated. Only an individually verified chart path is exempted from literal-number presence checks; a matching number elsewhere in slide prose does not inherit that exemption. Rebinding resets factual approval. Geometry repair carries bindings into its candidate and rechecks them before promotion.

```sh
python examples/calculated_pipeline.py --preview powerpoint
```

This offline synthetic example derives 25% growth from 100 and 125, stores the complete proof and previews a native editable chart. Omit preview where no engine exists. Human review remains pending: valid arithmetic and matching context cannot establish that the chosen source facts, metric relationship, category or negative-baseline interpretation are appropriate.

get_job now returns quality findings and calculation references alongside the manifest/deck, so an upstream agent can inspect failures without opening local JSON files. Saved job IDs are checked against the requested job before loading its report.
