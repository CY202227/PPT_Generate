"""Check the same subprocess transport an external agent uses."""

import asyncio
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def test_external_agent_startup(tmp_path):
    log = tmp_path / "startup.log"

    async def run():
        entry = Path(__file__).resolve().parents[1] / "start_demo.py"
        transport = StdioTransport(sys.executable, [str(entry)], cwd=str(tmp_path), log_file=log)
        async with Client(transport) as client:
            assert {tool.name for tool in await client.list_tools()} == {
                "create_ppt",
                "render_deck",
                "revise_slide",
                "get_deck_schema",
                "get_job",
                "read_document",
                "preview_ppt",
                "repair_ppt",
                "bind_evidence",
                "record_review",
                "submit_ppt",
                "get_task",
                "cancel_task",
                "cleanup_history",
                "cleanup_tasks",
                "get_slide",
                "preview_slide",
                "update_slide",
            }
            result = await client.call_tool("get_deck_schema", {})
            assert result.data["schema_version"] == "1.0"
            rendered = await client.call_tool(
                "render_deck",
                {
                    "deck": {
                        "schema_version": "1.0",
                        "title": "Agent preview",
                        "slides": [
                            {
                                "layout": "cover",
                                "title": "Agent preview",
                                "subtitle": "No Office required",
                            }
                        ],
                    }
                },
            )
            preview = await client.call_tool(
                "preview_slide", {"job_id": rendered.data["job_id"], "page_number": 1}
            )
            assert any(item.type == "image" for item in preview.content)
            assert preview.data["preview_backend"] == "native"

    asyncio.run(asyncio.wait_for(run(), timeout=30))
    output = log.read_text(encoding="utf-8")
    assert "waiting for agent requests" in output
    assert "FastMCP 4." in output
    for unwanted in ("DeprecationWarning", "Update available", "Deploy free", "3.0 is coming"):
        assert unwanted not in output
