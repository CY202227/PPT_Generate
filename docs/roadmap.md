# 0.5.0 release gates

0.5.0 is an alpha release candidate for personal decks and integration into another local agent. It does not promise production or enterprise design quality. A successful export is not a factual or visual approval.

## Required for the 0.5 milestone

- [x] Installable Python package, CLI and MCP stdio server.
- [x] Agent can render structured slide JSON, read job quality, receive individual slide images, update one page with revision protection and export editable PPTX.
- [x] Office-free preview is available from a single `mcp` extra install; PowerPoint and LibreOffice remain optional.
- [x] Human fact/visual review and native-renderer scope are represented separately in delivery status.
- [x] Bounded planning and explicit job/revision/preview/task retention policies.
- [x] English and Chinese setup docs, synthetic sample, seven native layout types and Apache-2.0 licensing.
- [ ] Latest version bump passes clean-install wheel smoke and remote CI on Windows/Linux and Python 3.10/3.12.
- [ ] Connect one real agent client using the documented stdio configuration and complete render → preview image → revise → export once.

The CI matrix checks package behavior, not real PowerPoint or LibreOffice installation on Linux. The native preview works there independently, but the font metrics and chart internals are estimates. The real-client check ensures MCP image content is actually usable in the selected host; generic stdio protocol tests do not certify every host's image rendering.

## After 0.5

- More diverse design criteria and rendered regression review for dense pages, label collisions and chart internals.
- LibreOffice actual-renderer smoke on a host with LibreOffice installed.
- Fact/source alignment for narrative claims, KPI/body calculations and translated or converted values.
- Explicit cost estimates by configured model/provider pricing and accurate stream/truncation diagnostics.
- Interactive human editing UI only if a concrete user workflow requires it; agents already revise through MCP.
- Template mapping, SmartArt, scheduled cleanup and finer retention of external-engine evidence.

The previous live-planning limitation remains relevant: varied reports can expose duplicate summaries, weak evidence framing or content that needs a person to reshape. A human must check whether a slide says the right thing and looks right before use.

## Observed live-planning limitation

The initial live output exposed duplicate summaries and source-compliance instructions in
audience-facing bullets. Regression rules now detect those cases and model planning sends
the findings back for bounded repair. A subsequent independent-report live run passed on its
first request and passed local PowerPoint layout measurements. Chinese/English fixtures and
a deliberately defective rendering probe have been checked locally; this remains a narrow
verification set, not production-quality certification. See docs/quality.md and the gallery.
