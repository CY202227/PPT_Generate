# Quality stages and evidence

Structural validation, editorial heuristics, engine layout measurements and human review are separate stages. `success` means an artifact or preview operation completed; it does not imply every quality stage passed.

## Editorial checks

Rules flag generation instructions in audience-facing text, pages made entirely of repeated disclosures, duplicated bullet/summary content and evidence pages without sources. Findings use page numbers and codes instead of reproducing private text. They may miss paraphrases or flag legitimate instructional decks.

Direct JSON rendering preserves user-authored content and records findings. Model planning feeds findings back with the previous rejected response and requests a complete corrected deck. There are at most three model calls, including the initial call. Rejected/accepted attempts, durations, reasons and provider token usage are saved in `planning.json` on successful jobs; failure diagnostics are returned as well. Raw prompts, responses and credentials are not in diagnostics.

`GENERATOR_REQUEST_TIMEOUT` defaults to 120 seconds and `GENERATOR_PLANNING_DEADLINE` to 360 seconds. SDK request retries are disabled so a bounded repair attempt does not hide extra requests. A caller may use longer limits for a slow provider. Unknown token usage is omitted, not represented as zero. Token counts are not monetary pricing estimates.

Schema, page-count, capacity and editorial errors participate in the same repair loop. Provider/authentication failures do not trigger repeated repair requests. A total deadline cancels the active wait. Factual accuracy remains explicitly unverified.

## Preview checks

PowerPoint exports real pages and measures text bounds against actual textbox/cell capacity, ink overlap among ordinary textboxes, and slide object bounds. Table-cell text coordinates are local to the cell and are deliberately excluded from cross-object overlap checks. Chart-internal labels are not included in the measured text collection.

LibreOffice exports a PDF using a separate process profile and renders it through PyMuPDF. It checks extracted PDF text bounds and page count. It does not promise textbox capacity/overlap detection. This backend has automated adapter tests but has not been live-tested on this Windows development host.

The default `auto` backend is now `native`: exported PPTX geometry and editable text/table/chart data are resolved into SVG and rendered to PNG by PyMuPDF. This works without Office, LibreOffice or browser control. Its text capacity/overlap checks estimate font metrics; chart internals and fonts can differ from Office. The report states `office_verification: not_performed`. MCP returns page images directly and the HTML gallery supports human inspection. Neither preview nor successful repair grants automatic human review approval. Native and PowerPoint text-capacity reports can drive the bounded repair loop; optional Office issues remain blockers even after another native preview.

External engine commands run in an isolated process group. On timeout or interruption, cleanup sends a graceful signal and then terminates the group before releasing the cross-process renderer lock. PowerPoint and LibreOffice previews run synchronously and cannot be force-cancelled through the generation queue; the configured engine timeout bounds their run. Temporary revision staging is removed when the call returns or times out. A PowerPoint COM server started outside the command's process tree may still require manual inspection if Office itself hangs.

Preview snapshots are bound to a revision. A failed preview leaves the current manifest/PPTX intact. A new content revision does not inherit old preview success. `visual_review` remains `required`, even when measured checks pass.

## Local verification

The Chinese eight-page model-planned report and the five-page English/negative-value fixture were rendered in Windows PowerPoint and passed measured checks. The earlier instruction/duplicate failure is represented in regression tests. A deliberately defective file containing oversized text, overlapping text and an out-of-slide object was detected by the real PowerPoint backend (`tools/preview_probe.py`).

The successful live planning result used one request and supplied provider usage: 2,866 prompt tokens, 6,696 completion tokens, 9,562 total, about 119 seconds. An earlier request timed out; a retry with an explicitly longer local request limit succeeded. These observations describe one local provider run, not a throughput/latency benchmark or a reliability guarantee.

Gallery assets contain simulated data created by this project; third-party Microsoft reference images are excluded.

## Unified delivery status and numeric source checks

Every newly published manifest and quality report contains `delivery`: `blocked` when editorial, numeric evidence or measured layout issues exist, otherwise `needs_review`. `ready` becomes true only after explicitly recorded human factual/visual approvals, source checks, required chart bindings and engine preview are present with no known blockers. `success` still means artifact creation succeeded. Agents should inspect `delivery`, not infer deliverability from `success`.

Model-generated jobs save the supplied material locally as `source.txt`, together with a SHA-256 digest and page-level numeric-literal audit in the quality report. This is sensitive job data; output directories should be treated like the original report. Revisions recheck the same material. Direct Python callers can pass `source_material` to `DeckPipeline.render`, and MCP callers can supply the same optional argument to `render_deck`; without it, source checks are explicitly pending. Number matching checks visible body text and native chart values. Numbers absent from material are flagged, including derived values without a validated derivation. Matching numbers do not verify metric, unit, period, sign interpretation or semantic claims. No factual certification is claimed.

MCP rendering and editing no longer share a server-wide write lock with previews. Per-job publication locks preserve revision consistency. Preview engines have a cross-process application lock that remains held until the worker exits even when its asynchronous caller cancels. A running preview still locks that same job; unrelated jobs can proceed. Cancellation does not terminate the external engine safely, and automatic repair handles measured PowerPoint overflow and conservative object positioning. Cross-platform live testing remains deferred; no WSL installation is required.

## Targeted overflow repair

The `repair` CLI and `repair_ppt` MCP tool consume a prior failing native or PowerPoint preview. Only flagged pages and objects are changed; font repair supports textboxes and table cells, geometry repair repositions objects without resizing or changing content. Unknown inherited sizes, oversized objects, crowded layouts without a safe placement and chart labels are declined. Flagged objects may be moved inside slide bounds or beside an overlapping textbox, only if their complete bounding rectangle avoids other objects. The strategy never increases fonts or lowers top-region text below 24 pt/body text below 18 pt. These floors are safeguards, not aesthetic certification.

Each candidate retains the original deck, text, numeric values and source report. It is previewed at most twice and accepted only with no measured layout issues and no known editorial/evidence blockers. The original job lock is acquired only for final promotion with an optimistic revision check; failed engines, unsupported defects, exhausted attempts or concurrent edits leave the original manifest intact. Failed candidate files and diagnostics remain available under repair-candidates. Explicit dry-run-first history cleanup is available; no scheduled automatic cleanup exists. An accepted repair records font adjustments in repair.json; subsequent content revisions return to standard renderer styling and require another preview.

The opt-in Windows probe tools/repair_probe.py inflates one title to 100 pt, verifies real PowerPoint detects overflow, repairs it, and verifies measured checks pass while text and the untouched cover slide remain unchanged. No LLM request is used.

## Exact chart evidence and review records

bind_evidence accepts at most 960 path/start/quote references. Offsets are zero-based characters in saved source.txt; extraction headers are part of this text. The exact quote must match at that offset and contain the bound number plus chart series, category, unit and period terms. Repeated references, invalid paths and mismatched quotes are rejected or blocked. Incomplete chart coverage is pending. Exact contextual checks do not establish relationships, causal claims, translations; explicit derivations additionally verify whitelisted decimal arithmetic, and human factual review remains required. Quoted data are stored only in the local bindings artifact, not diagnostic messages.

record_review requires a reviewer label, approved/rejected decision, factual_review/visual_review kind and current base revision. Factual approval requires saved material; visual approval requires a preview. Rejections and known automated defects block delivery. Approvals cannot override those defects. The tool documents that upstream agents must only record explicitly provided human results; identity is not authenticated. Tests use simulated reviewer data only. Content revisions reset all evidence bindings and reviews; a new preview resets visual approval, evidence rebinding resets factual approval. Repair promotion checks the whole saved manifest to avoid overwriting a review recorded while measuring a candidate.

The PDF and DOCX offline document examples both passed real Windows PowerPoint measured checks. KPI and timeline layouts, plus a combined overflow/overlap/bounds repair probe, have also passed local PowerPoint measurement. These remain synthetic examples, not a broad factual or aesthetic certification.

## Task lifecycle and retention

The persisted queue permits cancellation only before atomic export, bounds active tickets and serializes queue ownership per output root. Stopped planning becomes interrupted and requires explicit resubmission, avoiding unexpected repeated provider spend. Export job IDs are persisted before writing artifacts so completed publication can be recovered after a crash. Tickets contain source material and must be protected like original reports. Status responses omit request text. Orderly MCP shutdown waits for exports; abrupt process termination and PowerPoint cancellation are not claimed to be safely stoppable.

Retention cleanup is opt-in and dry-run by default. It locks the job, protects the current and referenced revisions, keeps recent history and only considers terminal repair candidates, unreferenced current preview/review snapshots and terminal task tickets. Absolute resolved target and child paths must remain within the job; symlinks and Windows reparse points are rejected before deletion. Scheduled cleanup is not implemented.

## Calculation evidence

Calculated chart bindings use path/derivation, where derivation has operation, precision and inputs. Inputs declare value/start/quote/category/unit/period; the metric is the chart series name and must occur in each exact source quote. The public schema is returned by get_deck_schema. sum permits 2–8 inputs; difference/ratio/percentage/percentage_change require two in the documented order. Decimal operands are finite, at most 30 digits, bounded in absolute size to 1e18 and, when nonzero, at least 1e-12. Precision is 0–6 decimal places, rounding ROUND_HALF_UP with a bounded decimal context.

Valid computation references retain the operation, rounding, target context, input locations and calculated value. They exempt only the exact bound chart value from unsupported-numeric-literal findings. Errors leave the numeric gate blocked; even approved manual review cannot bypass a bad proof. Quotes stay in the local bindings artifact; error messages do not reproduce them. A repaired PPTX inherits and revalidates bindings, then remaps artifact paths at promotion. Content revisions still clear old proofs and approvals.

Source provenance and arithmetic are verified mechanically. Choosing appropriate operands, interpreting relationships and negative baselines, translating labels and unit conversions are outside this audit. Factual/visual human review remains mandatory. The two-page offline growth example passed real Windows PowerPoint layout checks with no model request.
