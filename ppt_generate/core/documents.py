"""Bounded text extraction. Scanned PDFs require external OCR."""

from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 100_000


def extract_document(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("Source document does not exist")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Document exceeds 10 MiB limit")
    extension = path.suffix.lower()
    if extension in {".txt", ".md"}:
        content = path.read_text(encoding="utf-8-sig")
        pages = None
    elif extension == ".pdf":
        try:
            import fitz
        except ImportError as error:
            raise ValueError("Install ppt-generate[documents] for PDF extraction") from error
        with fitz.open(path) as document:
            if document.needs_pass:
                raise ValueError("Encrypted PDFs are unsupported")
            if len(document) > 100:
                raise ValueError("PDF exceeds 100 page limit")
            pages = len(document)
            chunks = []
            total = 0
            has_text = False
            for index, page in enumerate(document, 1):
                text = page.get_text()
                has_text = has_text or bool(text.strip())
                total += len(text)
                if total > MAX_CHARS:
                    raise ValueError("Document exceeds 100,000 character limit")
                chunks.append(f"## Page {index}\n{text}")
            if not has_text:
                raise ValueError("PDF has no extractable text; run OCR externally")
            content = "\n\n".join(chunks)
    elif extension == ".docx":
        try:
            from docx import Document
        except ImportError as error:
            raise ValueError("Install ppt-generate[documents] for DOCX extraction") from error
        from zipfile import ZipFile

        with ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError("Expanded DOCX exceeds 50 MiB limit")
        document = Document(path)
        chunks = []
        for block in document.iter_inner_content():
            if hasattr(block, "rows"):
                chunks.extend(" | ".join(cell.text for cell in row.cells) for row in block.rows)
            elif block.text.strip():
                chunks.append(block.text)
        content, pages = "\n\n".join(chunks), None
    else:
        raise ValueError("Supported inputs: .md, .txt, .pdf, .docx")
    if not content.strip():
        raise ValueError("Source document is empty")
    if len(content) > MAX_CHARS:
        raise ValueError("Document exceeds 100,000 character limit")
    return {
        "source": path.name,
        "format": extension[1:],
        "pages": pages,
        "characters": len(content),
        "text": content,
    }
