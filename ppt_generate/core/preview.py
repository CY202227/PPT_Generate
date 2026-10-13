"""Actual rendering with optional local engines; core rendering stays engine independent."""

import json
import os
import shutil
import signal
import subprocess
import tempfile
from importlib.resources import as_file, files
from pathlib import Path

from filelock import FileLock
from PIL import Image
from pptx import Presentation


class PreviewUnavailable(RuntimeError):
    pass


def _stop_process_tree(process):
    """Stop only the engine process group created for this preview request."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.wait(timeout=3)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        # The group leader may exit before its descendants; terminate the whole group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run(command, timeout):
    options = {
        "shell": False,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **options)
    except OSError as error:
        raise PreviewUnavailable("Preview engine unavailable or timed out") from error
    try:
        _, _ = process.communicate(timeout=timeout)
    except BaseException as error:
        _stop_process_tree(process)
        if isinstance(error, subprocess.TimeoutExpired):
            raise PreviewUnavailable("Preview engine unavailable or timed out") from error
        raise
    if process.returncode:
        # Do not include source paths/content from external application logs in public errors.
        raise PreviewUnavailable("Preview engine failed; verify the local engine installation")


def render_preview(pptx_path, output_directory, backend="auto", timeout=120):
    if backend in {"auto", "native"}:
        return _render_preview(pptx_path, output_directory, "native", timeout)
    # Engine ownership lasts until the worker finishes, even if its async caller cancels.
    # Serialize application access across MCP servers, not unrelated deck rendering.
    lock = Path(tempfile.gettempdir()) / "ppt-generate-preview-engine.lock"
    with FileLock(lock, timeout=timeout):
        return _render_preview(pptx_path, output_directory, backend, timeout)


def _render_preview(pptx_path, output_directory, backend="auto", timeout=120):
    pptx = Path(pptx_path).resolve()
    output = Path(output_directory).resolve()
    if backend not in {"auto", "native", "powerpoint", "libreoffice"}:
        raise ValueError("backend must be auto, native, powerpoint or libreoffice")
    if backend == "auto":
        backend = "native"
    output.mkdir(parents=True, exist_ok=True)
    if backend == "native":
        from .native_preview import render_native

        report = render_native(pptx, output)
    elif backend == "powerpoint":
        if os.name != "nt":
            raise PreviewUnavailable("PowerPoint previews require Windows and PowerPoint")
        with as_file(files("ppt_generate.resources").joinpath("powerpoint_preview.ps1")) as script:
            _run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(script),
                    "-PptxPath",
                    str(pptx),
                    "-OutputDirectory",
                    str(output),
                ],
                timeout,
            )
        report = json.loads((output / "report.json").read_text(encoding="utf-8-sig"))
    else:
        executable = shutil.which("soffice") or shutil.which("libreoffice")
        if not executable:
            raise PreviewUnavailable("LibreOffice is not available on PATH")
        try:
            import fitz
        except ImportError as error:
            raise PreviewUnavailable(
                "Install ppt-generate[preview] for LibreOffice PDF rendering"
            ) from error
        profile = output / ".lo-profile"
        _run(
            [
                executable,
                "--headless",
                "-env:UserInstallation=" + profile.as_uri(),
                "--convert-to",
                "pdf",
                "--outdir",
                str(output),
                str(pptx),
            ],
            timeout,
        )
        pdf = output / (pptx.stem + ".pdf")
        if not pdf.is_file():
            raise PreviewUnavailable("LibreOffice did not produce a PDF")
        pages, issues = [], []
        with fitz.open(pdf) as document:
            for number, page in enumerate(document, 1):
                file_name = f"slide-{number:03d}.png"
                page.get_pixmap(
                    matrix=fitz.Matrix(1600 / page.rect.width, 1600 / page.rect.width)
                ).save(output / file_name)
                for block in page.get_text("blocks"):
                    if (
                        block[0] < -1
                        or block[1] < -1
                        or block[2] > page.rect.width + 1
                        or block[3] > page.rect.height + 1
                    ):
                        issues.append({"page": number, "code": "pdf_text_out_of_bounds"})
                pages.append({"page": number, "file": file_name})
        report = {
            "backend": "libreoffice",
            "status": "issues_found" if issues else "passed",
            "pages": pages,
            "issues": issues,
            "scope": "rendered PDF page count and text page bounds",
            "limitations": [
                "Textbox overflow, chart labels, overlaps and aesthetics are not certified by this backend"
            ],
            "visual_review": "required",
        }
    expected = len(Presentation(pptx).slides)
    if len(report["pages"]) != expected:
        raise PreviewUnavailable("Preview page count does not match the PPTX")
    for page in report["pages"]:
        name = page["file"]
        if Path(name).name != name or not name.endswith(".png"):
            raise PreviewUnavailable("Invalid preview file name from engine")
        with Image.open(output / name) as image:
            image.verify()
    report["slide_count"] = expected
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
