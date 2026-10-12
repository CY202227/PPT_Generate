import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("format", ["md", "pdf", "docx"])
def test_document_to_evidence_bound_deck(tmp_path, format):
    path = Path(__file__).resolve().parents[1] / "examples/document_pipeline.py"
    spec = importlib.util.spec_from_file_location("document_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(tmp_path, format)
    quality = json.loads(Path(result["quality_report"]).read_text(encoding="utf-8"))
    assert result["slide_count"] == 5
    assert quality["provenance"]["status"] == "context_checks_passed"
    assert len(quality["provenance"]["references"]) == 3
    assert not result["delivery"]["blocked_by"]
    assert not result["delivery"]["ready"]
