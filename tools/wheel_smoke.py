"""Run using a clean environment with an installed wheel, never an editable checkout."""

import json
import tempfile
from pathlib import Path

from pptx import Presentation

from ppt_generate import DeckPipeline
from ppt_generate.core.deck import get_schema


def main():
    assert get_schema()["$defs"]["chart"]
    deck = {
        "schema_version": "1.0",
        "title": "Wheel smoke",
        "slides": [
            {"layout": "cover", "title": "Installed package"},
            {
                "layout": "chart",
                "title": "Editable evidence",
                "unit": "units",
                "period": "Q1–Q2",
                "categories": ["Q1", "Q2"],
                "series": [{"name": "Sample", "values": [10, 12]}],
            },
        ],
    }
    with tempfile.TemporaryDirectory() as directory:
        result = DeckPipeline(directory).render(deck)
        assert len(Presentation(result["exported_file"]).slides) == 2
        assert json.loads(Path(result["deck_file"]).read_text(encoding="utf-8")) == deck
    print("Installed wheel smoke passed")


if __name__ == "__main__":
    main()
