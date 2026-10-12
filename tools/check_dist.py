"""Reject accidental private files and legacy code in release artifacts."""

import tarfile
from pathlib import Path
from zipfile import ZipFile


def main():
    for artifact in Path("dist").glob("*"):
        if artifact.suffix == ".whl":
            with ZipFile(artifact) as archive:
                names = archive.namelist()
                assert "ppt_generate/resources/deck.schema.json" in names
                assert "ppt_generate/resources/powerpoint_preview.ps1" in names
                assert any(name.endswith("/licenses/NOTICE") for name in names)
        elif artifact.name.endswith(".tar.gz"):
            with tarfile.open(artifact) as archive:
                names = archive.getnames()
        else:
            continue
        forbidden = {".env", "outputs", "legacy", "benchmarks", ".venv", "tmp"}
        assert not any(forbidden.intersection(Path(name).parts) for name in names), names
    print("Distribution contents verified")


if __name__ == "__main__":
    main()
