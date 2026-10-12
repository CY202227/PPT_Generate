import json

import pytest

from ppt_generate import DeckPipeline
from ppt_generate.core.evidence import audit_bindings


def chart():
    return {
        "schema_version": "1.0",
        "title": "Report",
        "slides": [
            {
                "layout": "chart",
                "title": "Revenue",
                "unit": "CNY",
                "period": "2026",
                "categories": ["Q1"],
                "series": [{"name": "Revenue", "values": [150]}],
                "source": "Synthetic data",
            }
        ],
    }


def binding(quote):
    return [{"path": "/slides/0/series/0/values/0", "start": 0, "quote": quote}]


def test_same_number_different_context_and_tampered_quote():
    deck = chart()
    wrong = "2026 Q1 Customers 150 people"
    report = audit_bindings(deck, wrong, binding(wrong))
    assert {x["code"] for x in report["issues"]} == {"bound_metric_missing", "bound_unit_missing"}
    correct = "2026 Q1 Revenue 150 CNY"
    assert audit_bindings(deck, correct, binding(correct))["status"] == "context_checks_passed"
    assert (
        audit_bindings(deck, wrong, binding(correct))["issues"][0]["code"]
        == "source_quote_mismatch"
    )
    assert audit_bindings(deck, correct, [])["status"] == "incomplete"
    with pytest.raises(ValueError):
        audit_bindings(deck, correct, binding(correct) * 2)


def test_reviews_are_explicit_bound_to_revision_and_do_not_override_checks(tmp_path, monkeypatch):
    pipeline = DeckPipeline(tmp_path)
    source = "2026 Q1 Revenue 150 CNY"
    saved = pipeline.render(chart(), source_material=source)
    job, revision = saved["job_id"], saved["revision"]

    def preview(pptx, output, backend):
        report = {"backend": "powerpoint", "status": "passed", "pages": [], "issues": []}
        (output / "report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr("ppt_generate.core.preview.render_preview", preview)
    with pytest.raises(ValueError, match="preview"):
        pipeline.record_review(job, "visual_review", "approved", "Test reviewer", revision)
    pipeline.preview(job)
    pipeline.bind_evidence(job, binding(source), revision)
    pipeline.record_review(job, "factual_review", "approved", "Test reviewer", revision)
    result = pipeline.record_review(job, "visual_review", "approved", "Test reviewer", revision)
    assert result["delivery"]["ready"]
    result = pipeline.preview(job)
    assert result["delivery"]["pending"] == ["visual_review"]
    pipeline.record_review(job, "visual_review", "rejected", "Test reviewer", revision)
    assert "visual_review" in pipeline.get_job(job)["manifest"]["delivery"]["blocked_by"]
    changed = pipeline.revise(job, 1, {**chart()["slides"][0], "title": "Updated"})
    assert not changed["delivery"]["ready"]
    with pytest.raises(ValueError, match="revision conflict"):
        pipeline.record_review(job, "factual_review", "approved", "Test reviewer", revision)


def test_invalid_bindings_block_even_with_manual_approvals(tmp_path, monkeypatch):
    pipeline = DeckPipeline(tmp_path)
    source = "2026 Q1 Revenue 150 CNY"
    saved = pipeline.render(chart(), source_material=source)
    job, revision = saved["job_id"], saved["revision"]
    result = pipeline.bind_evidence(job, binding("2026 Q1 Revenue 999 CNY"), revision)
    assert result["delivery"]["status"] == "blocked"
    result = pipeline.record_review(job, "factual_review", "approved", "Test reviewer", revision)
    assert "provenance" in result["delivery"]["blocked_by"]
    assert not result["delivery"]["ready"]
