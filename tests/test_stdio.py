"""Check the same subprocess transport an external agent uses."""

import asyncio
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def test_external_agent_startup(tmp_path):
    async def run():
        entry = Path(__file__).resolve().parents[1] / "start_demo.py"
        transport = StdioTransport(sys.executable, [str(entry)], cwd=str(tmp_path))
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
            }
            result = await client.call_tool("get_deck_schema", {})
            assert result.data["schema_version"] == "1.0"

    asyncio.run(asyncio.wait_for(run(), timeout=30))
