import asyncio
import threading

from ppt_generate.mcp.server import PPTGenerateServer


def test_preview_does_not_block_another_job(tmp_path, monkeypatch):
    server = PPTGenerateServer(tmp_path)
    started, release = threading.Event(), threading.Event()

    def preview(*args):
        started.set()
        assert release.wait(10)
        return {"success": True}

    monkeypatch.setattr(server.pipeline, "preview", preview)

    async def scenario():
        preview_tool = await server.app.get_tool("preview_ppt")
        render_tool = await server.app.get_tool("render_deck")
        task = asyncio.create_task(preview_tool.fn("a" * 32))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            result = await asyncio.wait_for(
                render_tool.fn(
                    {
                        "schema_version": "1.0",
                        "title": "Independent",
                        "slides": [{"layout": "cover", "title": "Independent"}],
                    }
                ),
                timeout=5,
            )
            assert result["success"]
            assert not task.done()
        finally:
            release.set()
            await task

    asyncio.run(scenario())
