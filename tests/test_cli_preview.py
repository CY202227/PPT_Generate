import json

import pytest

from ppt_generate.cli import main
from ppt_generate.core.preview import PreviewUnavailable


def test_requested_preview_failure_still_returns_generated_artifact(tmp_path, monkeypatch, capsys):
    source = tmp_path / "deck.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "title": "Report",
                "slides": [{"layout": "cover", "title": "Report"}],
            }
        ),
        encoding="utf-8",
    )

    def missing(*args, **kwargs):
        raise PreviewUnavailable("Engine missing")

    monkeypatch.setattr("ppt_generate.core.preview.render_preview", missing)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ppt-generate",
            "render",
            str(source),
            "--output-root",
            str(tmp_path / "jobs"),
            "--preview-backend",
            "libreoffice",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["success"] is True
    assert result["exported_file"]
    assert result["preview_error"]["code"] == "preview_unavailable"
