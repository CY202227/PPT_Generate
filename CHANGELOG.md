# Changelog

## 0.5.0 — unreleased alpha

- Make the MCP install include the Office-independent preview dependency, so agents can receive slide images after a single documented install.
- Document the full agent loop from JSON or model planning through inline preview, revision-protected editing and editable PPTX export.
- Align package metadata, CLI version and English/Chinese documentation on 0.5.0.
- Terminate isolated external renderer process groups on timeout/interruption and clean incomplete revision staging.
- Explicit retention for unreferenced preview/review snapshots and terminal task tickets; protect active work and reject linked cleanup targets.

## 0.4.0 — unreleased

- Explicit current preview/review snapshot and terminal task-ticket retention, with active/reference protection.
- Reject Windows junctions in cleanup and queue records; workers tolerate removal of cancelled tickets.
- Run external preview engines in isolated process groups and terminate descendants on timeout/interruption.

- Office-independent default SVG/PNG preview and offline HTML gallery from exported PPTX geometry.
- MCP single-page reading, inline image previews and revision-protected editing with editable export.
- Native preview repair support; preserve optional Office issues as delivery blockers.

- Source-backed decimal chart calculations with explicit operands, rounding and path-scoped numeric exemptions.
- Public evidence schema and proof-preserving layout repair; reproducible calculated-growth example.
- Agent-readable quality reports in get_job and matching saved job identity checks.

- Migrate MCP dependency to FastMCP >=4.1,<5 and MCP SDK v2.
- Quiet stdio startup banner, explicit installed version/wait state, and startup log regression checks.

- Adaptive page budgets for CLI/MCP generation with exact-count compatibility mode.
- Persisted bounded MCP generation queue, planning cancellation, export recovery and orderly shutdown.
- Explicit dry-run-first revision/terminal-candidate cleanup with path/link guards.
- Foundation branch published and verified on remote Windows/Linux Python 3.10/3.12 CI.


- Exact chart/source quote bindings with offsets and metric/category/unit/period checks.
- Explicit revision-bound human review records and delivery readiness gates.
- Conservative overlap/bounds repositioning and paragraph font inheritance in measured repair.
- Editable KPI/timeline layouts and reproducible PDF/DOCX/Markdown ingestion examples.
- Real PowerPoint probes for all three supported defects and additional layouts.

## 0.3.0 — unreleased

- Unified delivery gate, source fingerprints and conservative numeric checks repeated on revision.
- Independent MCP job writes and cross-process preview engine coordination.

- Page-specific editorial checks with bounded model repair and planning/token diagnostics.
- Configurable per-request and total planning timeouts; no hidden SDK retries.
- Version-bound PowerPoint and LibreOffice preview backends with explicit measurement scopes.
- CLI/MCP preview integration and preview failure rollback.
- Dark cover, larger sparse-page text, consistent East Asian fonts, word-aware wrapping and editable chart labels.
- Chinese/English/negative-value regression fixtures and a real-engine defect-detection probe.
- Content-preserving PowerPoint overflow repair via CLI/MCP, bounded candidate previews and conflict-safe promotion.
- Human aesthetic/factual review remains required; overlap, bounds and chart-label repair are not implemented.

## 0.2.0 — unreleased

- Installable `ppt_generate` package with CLI and optional MCP/LLM/document extras.
- Bundled JSON Schema 1.0; rejects fields a renderer would otherwise discard.
- Editable cover, bullet, split, table and chart layouts.
- Persistent job lookup, atomic revision publication, cross-process locks and optional revision conflict checks.
- Bounded Markdown, TXT, PDF and DOCX extraction.
- Stable CLI/MCP error codes and explicit configuration-file loading.
- Offline tests, lint/format checks, wheel/source distribution checks and a Linux/Windows CI matrix.
- Legacy template/Marp paths moved out of the supported package.

Breaking changes: import `ppt_generate` instead of `src`; use `ppt-generate render` instead of the old positional script; MCP `error` is now an object with `code` and `message`; dotenv files require explicit selection.

Rendering remains alpha. Actual font overflow checks, automatic visual repair, template preservation and quality certification are not implemented.
