# Release gates

## Completed locally for the alpha

- Installable package and bundled contract.
- Offline editable-rendering and revision tests.
- Optional model, MCP and document integrations.
- Local Windows actual-PowerPoint preview inspection.
- CI definition for Windows/Linux and Python 3.10/3.12.

The foundation commit passed GitHub CI on Windows/Linux Python 3.10/3.12. Real Office/LibreOffice rendering on those remote runners remains unverified.

## Required before calling output production quality

- Expand font-aware checks across fonts/platforms and chart-internal labels beyond the initial PowerPoint checks.
- Diverse independent report fixtures: English, Chinese, dense tables, long labels, negative/missing numeric values and different page counts.
- A rendered regression gallery reviewed against stated enterprise presentation criteria.
- Live-test the LibreOffice backend and extend the editorial/capacity repair loop to actual preview feedback.
- Fact/source alignment evaluation on reports not already formatted as slide JSON.
- Realistic provider timeout, response truncation, cancellation and cost visibility.

## Subsequent scope

- Template mapping with explicit supported/unsupported objects.
- Scheduled cleanup and finer retention of Office preview evidence (explicit old revision, terminal candidate, current unused preview/review snapshot and terminal ticket cleanup is implemented).
- Native KPI and richer comparison layouts.
- Configurable typography/theme, source citations and evidence preservation.

The alpha is a reusable engineering foundation. Adding license/CI files does not establish enterprise presentation quality.

## Observed live-planning limitation

The initial live output exposed duplicate summaries and source-compliance instructions in
audience-facing bullets. Regression rules now detect those cases and model planning sends
the findings back for bounded repair. A subsequent independent-report live run passed on its
first request and passed local PowerPoint layout measurements. Chinese/English fixtures and
a deliberately defective rendering probe have been checked locally; this remains a narrow
verification set, not production-quality certification. See docs/quality.md and the gallery.
