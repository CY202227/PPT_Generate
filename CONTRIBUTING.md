# Contributing

Install Python 3.10+ and create a virtual environment. From a checkout:

```sh
python -m pip install -e ".[llm,mcp,documents,dev]"
python -m ruff check ppt_generate tests tools start_demo.py
python -m ruff format --check ppt_generate tests tools start_demo.py
python -m pytest -q
python -m build
python tools/check_dist.py
```

Tests are offline. Never put provider credentials or real customer material in fixtures, screenshots, logs or pull requests. Live provider smoke runs are explicit and excluded from CI.

Include a reproducible input, the observed result, and the expected result in a bug report. For rendering issues, include a sanitized preview and the PowerPoint/LibreOffice version and available fonts.

When changing the interchange contract, update `tools/build_schema.py`, regenerate the bundled schema, and add rejection/round-trip tests. A breaking contract requires a schema version change. Unknown fields are rejected to avoid silently dropping content.

When adding a layout, keep text and data editable. Test actual objects and values in the resulting PPTX. A successful export does not establish visual quality: render the new layout and inspect it before submission.

Keep the pure rendering API independent of LLM and MCP extras. `legacy/` is archival code, not a supported public API.
