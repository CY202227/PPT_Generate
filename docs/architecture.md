# Architecture and supported contract

The pipeline has separate boundaries for source extraction, model planning, interchange validation, editable rendering and job storage. The model produces structured slide content; code controls geometry. Upstream agents can bypass planning and render their own JSON.

`ppt_generate/resources/deck.schema.json` is bundled in the wheel and returned by MCP. Draft 2020-12 validation controls shape and field limits. Additional validation enforces equal table row widths and chart category/value counts and rejects non-finite values. Unknown fields are rejected.

Planning uses an OpenAI-compatible chat completion endpoint and JSON response mode. It validates page count, conservative capacity and editorial rules before returning. Up to two additional requests may repair a rejected candidate using page-specific feedback and the previous response. SDK retries are disabled; an overall deadline bounds the loop. Attempts and token usage are recorded without storing prompts/responses in diagnostics. This is not proof of factual correctness.

Prompting also requests audience-facing writing, a summary-first narrative and distinct page
purposes. These are model instructions, not deterministic editorial guarantees. Known live
planning failures are recorded in the release gates instead of being hidden by export success.

Each job uses a random identifier and a random revision directory. A revision is written in a staging directory, renamed after success, then published through an atomic manifest replacement. Failed validation leaves the current manifest intact. Old revisions are retained. Independent MCP jobs can run concurrently; a filesystem lock protects each job across processes. A separate cross-process preview-engine lock coordinates application access. `base_revision` detects stale edits. A crashed process may leave an unreferenced revision or staging directory; explicit dry-run-first history cleanup is available; scheduled garbage collection is not implemented.

Job loading derives the deck path from a validated revision identifier rather than trusting an arbitrary stored absolute path. The configured output root is a trusted storage location. Filesystem symlinks and malicious modifications to that root are outside the local trust model.

Quality reports separate structural/capacity checks, editorial heuristics, actual engine measurements and human visual review. The renderer's pre-export capacity check remains an estimate. Optional PowerPoint previews measure real text bounds and ordinary textbox overlap; LibreOffice's PDF checks have a narrower scope. Immutable preview snapshots are attached to the exact revision and stale previews do not transfer to edits. CI verifies adapter behavior and editable data; local real-engine checks and their limits are described in docs/quality.md.

Optional extras keep basic rendering independent of model providers and MCP. The `mcp` extra includes PyMuPDF so the default no-Office preview tool works after a single MCP install; the standalone API/CLI preview remains in the `preview` extra. Source material is sent externally only by planning. The package never loads a repository `.env` implicitly; use environment variables, `PPT_GENERATE_ENV_FILE`, or the CLI's `--env-file`.

## Office-independent preview and MCP editing

Planning, slide revision, native editable PPTX export and the default SVG/PNG preview work without PowerPoint or LibreOffice. The preview extra supplies PyMuPDF for PNG rendering; no browser automation is required. Optional PowerPoint/LibreOffice checks provide additional actual-PPTX rendering evidence. Human factual and visual review remains required.

MCP get_slide reads structured content and resolved geometry; preview_slide returns an inline PNG image plus SVG and an offline HTML gallery; update_slide requires the current revision, changes one page, exports native PPTX and returns its new preview. Agents use these tools directly, without clicking a browser. Text-only clients can use the structured scene. The HTML gallery is a read-only human viewing surface; an interactive browser editor remains future work.

The native preview reads positions, fonts, table cells and chart data from the exported PPTX, including geometry changed by repair. Its font measurements and chart internals are approximations, not actual Office rendering. Reports record that scope and require human review. Known issues from an optional Office check remain blockers after a later native preview.
