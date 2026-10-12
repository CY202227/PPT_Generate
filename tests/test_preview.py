import json
from pathlib import Path

import pytest
from PIL import Image

from ppt_generate import DeckPipeline
from ppt_generate.core.preview import PreviewUnavailable, render_preview


def _deck():
    return {
        "schema_version": "1.0",
        "title": "Preview",
        "slides": [{"layout": "cover", "title": "Preview"}],
    }


def test_preview_failure_preserves_published_job(tmp_path, monkeypatch):
    pipeline = DeckPipeline(tmp_path)
    saved = pipeline.render(_deck())
    manifest = tmp_path / saved["job_id"] / "manifest.json"
    before = manifest.read_bytes()

    def fail(*args):
        raise PreviewUnavailable("Engine missing")

    monkeypatch.setattr("ppt_generate.core.preview.render_preview", fail)
    with pytest.raises(PreviewUnavailable):
        pipeline.preview(saved["job_id"])
    assert manifest.read_bytes() == before
    assert Path(saved["exported_file"]).is_file()
    assert not list(tmp_path.rglob(".tmp-preview-*"))


def test_preview_evidence_is_version_bound(tmp_path, monkeypatch):
    pipeline = DeckPipeline(tmp_path)
    saved = pipeline.render(_deck())

    def fake(pptx, output, backend):
        Image.new("RGB", (160, 90), "white").save(output / "slide-001.png")
        report = {
            "backend": "test_engine",
            "status": "issues_found",
            "pages": [{"page": 1, "file": "slide-001.png"}],
            "issues": [{"page": 1, "code": "text_overflow"}],
            "scope": "test",
            "visual_review": "required",
        }
        (output / "report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr("ppt_generate.core.preview.render_preview", fake)
    preview = pipeline.preview(saved["job_id"], base_revision=saved["revision"])
    assert preview["revision"] == saved["revision"]
    assert preview["layout_review"] == "issues_found"
    assert preview["visual_review"] == "required"
    quality = json.loads(Path(preview["quality_report"]).read_text(encoding="utf-8"))
    assert quality["layout"]["issues"][0]["code"] == "text_overflow"
    assert Path(preview["preview_files"][0]).is_file()
    updated = pipeline.revise(saved["job_id"], 1, {"layout": "cover", "title": "Updated"})
    assert "preview_files" not in updated
    with pytest.raises(ValueError, match="revision conflict"):
        pipeline.preview(saved["job_id"], base_revision=saved["revision"])


def test_missing_libreoffice_is_actionable(tmp_path, monkeypatch):
    saved = DeckPipeline(tmp_path).render(_deck())
    monkeypatch.setattr("ppt_generate.core.preview.shutil.which", lambda _: None)
    with pytest.raises(PreviewUnavailable, match="PATH"):
        render_preview(saved["exported_file"], tmp_path / "preview", "libreoffice")


def test_libreoffice_pdf_adapter_and_page_count(tmp_path, monkeypatch):
    import fitz

    saved = DeckPipeline(tmp_path).render(_deck())
    commands = []
    monkeypatch.setattr("ppt_generate.core.preview.shutil.which", lambda _: "test-soffice")

    def convert(command, timeout):
        commands.append(command)
        output = Path(command[command.index("--outdir") + 1])
        with fitz.open() as document:
            document.new_page(width=960, height=540).insert_text((72, 72), "Rendered test page")
            document.save(output / "presentation.pdf")

    monkeypatch.setattr("ppt_generate.core.preview._run", convert)
    report = render_preview(saved["exported_file"], tmp_path / "converted", "libreoffice")
    assert report["status"] == "passed"
    assert report["slide_count"] == 1
    assert "--headless" in commands[0]
    assert any(arg.startswith("-env:UserInstallation=file:") for arg in commands[0])
    assert (tmp_path / "converted/slide-001.png").is_file()
    deck = _deck()
    deck["slides"] *= 2
    two = DeckPipeline(tmp_path).render(deck)
    with pytest.raises(PreviewUnavailable, match="page count"):
        render_preview(two["exported_file"], tmp_path / "count-mismatch", "libreoffice")
