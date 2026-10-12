import json
from pathlib import Path

from ppt_generate import DeckPipeline
from ppt_generate.core.quality import audit_numbers


def deck(value="收入150万元"):
    return {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [{"layout": "bullets", "title": "Results", "bullets": [value]}],
    }


def test_numeric_audit_is_conservative_and_private():
    report = audit_numbers(deck("收入999万元"), "Private revenue 150")
    assert report["status"] == "issues_found"
    assert report["issues"][0]["page"] == 1
    assert "Private" not in json.dumps(report)
    assert audit_numbers(deck(), "Revenue 150.0")["status"] == "literal_checks_passed"
    assert audit_numbers(deck(), "Revenue 150.")["status"] == "literal_checks_passed"
    assert audit_numbers(deck(), "Revenue 150")["factual_accuracy"] == "not_verified"


def test_revision_rechecks_source_and_cannot_inherit_quality(tmp_path):
    pipeline = DeckPipeline(tmp_path)
    original = pipeline.render(deck(), source_material="Revenue 150")
    assert original["delivery"]["status"] == "needs_review"
    changed = pipeline.revise(original["job_id"], 1, deck("收入999万元")["slides"][0])
    assert changed["delivery"]["status"] == "blocked"
    assert changed["delivery"]["blocked_by"] == ["evidence"]
    quality = json.loads(Path(changed["quality_report"]).read_text(encoding="utf-8"))
    assert quality["evidence"]["source_sha256"]
    assert Path(original["exported_file"]).is_file()


def test_missing_source_is_explicit(tmp_path):
    result = DeckPipeline(tmp_path).render(deck())
    assert "source_checks" in result["delivery"]["pending"]
    assert not result["delivery"]["ready"]
