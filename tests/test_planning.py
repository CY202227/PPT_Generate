import asyncio
import copy
import json
from types import SimpleNamespace

import openai
import pytest

from ppt_generate.core.pipeline import PlanningFailed, plan_deck
from ppt_generate.utils.config import config


def test_model_retries_invalid_page_count(monkeypatch):
    valid = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "cover", "title": "Report"}],
    }
    wrong = copy.deepcopy(valid)
    wrong["slides"] *= 2
    replies = [wrong, valid]
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=json.dumps(replies.pop(0))))
                ]
            )

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)
    monkeypatch.setattr(config.generator, "api_key", "test-placeholder")
    result = asyncio.run(plan_deck("Report", 1, "general", "Provided source data"))
    assert result == valid
    assert len(calls) == 2
    assert "Never put instructions" in calls[0]["messages"][1]["content"]
    assert "Validation failed" in calls[1]["messages"][-1]["content"]


def test_missing_evidence_does_not_call_model(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("Must not initialize model for invalid input")

    monkeypatch.setattr(openai, "AsyncOpenAI", forbidden)
    with pytest.raises(ValueError, match="research_report"):
        asyncio.run(plan_deck("Report", 1, "general", ""))


def test_editorial_feedback_repairs_and_records_attempts(monkeypatch):
    bad = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "bullets", "title": "Results", "bullets": ["Do not invent data"]}],
    }
    good = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "bullets", "title": "Results", "bullets": ["Revenue 150"]}],
    }
    replies, calls = [bad, good], []

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=json.dumps(replies.pop(0))))
                ],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=30, total_tokens=130),
            )

    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    monkeypatch.setattr(config.generator, "api_key", "test-placeholder")
    diagnostics = {}
    result = asyncio.run(
        plan_deck("Report", 1, "Management", "Revenue 150", diagnostics=diagnostics)
    )
    assert result == good
    assert [a["status"] for a in diagnostics["attempts"]] == ["rejected", "accepted"]
    assert diagnostics["attempts"][0]["issues"][0]["code"] == "instruction_echo"
    assert diagnostics["attempts"][1]["usage"]["total_tokens"] == 130
    assert calls[1]["messages"][-2]["role"] == "assistant"
    assert "instruction_echo" in calls[1]["messages"][-1]["content"]


def test_total_deadline_cancels_provider_wait(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def create(self, **kwargs):
            await asyncio.sleep(2)

    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    monkeypatch.setattr(config.generator, "api_key", "test-placeholder")
    monkeypatch.setattr(config.generator, "planning_deadline", 0.01)
    with pytest.raises(PlanningFailed, match="deadline") as error:
        asyncio.run(plan_deck("Report", 1, "Management", "Revenue 150"))
    assert error.value.diagnostics["status"] == "deadline_exceeded"


def test_provider_failure_records_diagnostics_without_raw_request(monkeypatch):
    import httpx

    from ppt_generate.core.errors import failure

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def create(self, **kwargs):
            raise openai.APITimeoutError(request=httpx.Request("POST", "http://private.invalid/v1"))

    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    monkeypatch.setattr(config.generator, "api_key", "test-placeholder")
    with pytest.raises(openai.APITimeoutError) as error:
        asyncio.run(plan_deck("Report", 1, "Management", "Revenue 150"))
    result = failure(error.value)
    assert result["error"]["code"] == "provider_unavailable"
    assert result["diagnostics"]["attempts"][0]["status"] == "provider_error"
    assert "private.invalid" not in json.dumps(result)
    assert "test-placeholder" not in json.dumps(result)


def test_repair_budget_exhaustion_returns_quality_failure(monkeypatch):
    from ppt_generate.core.errors import failure

    calls = []
    bad = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "bullets", "title": "Results", "bullets": ["Do not invent data"]}],
    }

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(bad)))]
            )

    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    monkeypatch.setattr(config.generator, "api_key", "test-placeholder")
    with pytest.raises(PlanningFailed) as error:
        asyncio.run(plan_deck("Report", 1, "Management", "Revenue 150", max_attempts=2))
    assert len(calls) == 2
    assert failure(error.value)["error"]["code"] == "quality_failed"
    assert [x["status"] for x in error.value.diagnostics["attempts"]] == ["rejected", "rejected"]
