import copy
import json
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

from ppt_generate.core.deck import get_schema, validate_deck
from ppt_generate.core.errors import failure
from ppt_generate.core.pipeline import DeckPipeline


def test_schema_is_valid_and_rejects_unused_fields():
    schema = get_schema()
    Draft202012Validator.check_schema(schema)
    deck = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "cover", "title": "Report"}],
    }
    assert validate_deck(deck) == deck
    deck["slides"][0]["bullets"] = ["This would be silently lost"]
    with pytest.raises(ValueError, match="schema constraint"):
        validate_deck(deck)


def test_revision_conflict(tmp_path):
    deck = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "cover", "title": "Report"}],
    }
    pipeline = DeckPipeline(tmp_path)
    original = pipeline.render(deck)
    pipeline.revise(
        original["job_id"], 1, {"layout": "cover", "title": "New"}, original["revision"]
    )
    with pytest.raises(ValueError, match="revision conflict"):
        pipeline.revise(original["job_id"], 1, deck["slides"][0], original["revision"])


def test_multi_process_edits_preserve_both_updates(tmp_path):
    deck = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "cover", "title": "Page A"}, {"layout": "cover", "title": "Page B"}],
    }
    pipeline = DeckPipeline(tmp_path)
    saved = pipeline.render(deck)
    code = "from ppt_generate import DeckPipeline; import sys; DeckPipeline(sys.argv[1]).revise(sys.argv[2],int(sys.argv[3]),{'layout':'cover','title':sys.argv[4]})"
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(tmp_path), saved["job_id"], str(page), title],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for page, title in [(1, "Updated A"), (2, "Updated B")]
    ]
    for process in processes:
        _, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr.decode(errors="replace")
    result = pipeline.get_job(saved["job_id"])
    assert [s["title"] for s in result["deck"]["slides"]] == ["Updated A", "Updated B"]


def test_manifest_cannot_redirect_deck_read(tmp_path):
    pipeline = DeckPipeline(tmp_path)
    deck = {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "cover", "title": "Report"}],
    }
    saved = pipeline.render(deck)
    manifest_path = tmp_path / saved["job_id"] / "manifest.json"
    manifest = copy.deepcopy(saved)
    manifest["deck_file"] = "outside.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert pipeline.get_job(saved["job_id"])["deck"] == deck


def test_remote_errors_do_not_echo_body():
    error = RuntimeError("provider body containing private document or credentials")
    result = failure(error)
    assert result["error"]["code"] == "internal_error"
    assert "credentials" not in json.dumps(result)


def test_cli_failure_exit_code(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "ppt_generate.cli", "validate", str(source)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["error"]["code"] == "invalid_input"
