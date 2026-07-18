import io
import fitz  # PyMuPDF
from docx import Document


class ScriptParser:
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".fountain"}
    # Markdown and Fountain are plain-text screenplay formats — decoded as-is
    _TEXT_EXTENSIONS = {".txt", ".md", ".fountain"}

    def parse_bytes(self, data: bytes, filename: str) -> str:
        ext = self._get_extension(filename)
        if ext == ".pdf":
            return self._parse_pdf(data)
        elif ext == ".docx":
            return self._parse_docx(data)
        elif ext == ".doc":
            # python-docx reads only the modern zip-based .docx — a legacy
            # binary .doc used to crash the request with an opaque 500
            raise ValueError("Legacy .doc is not supported. Save it as .docx "
                             "or PDF and upload again.")
        elif ext in self._TEXT_EXTENSIONS:
            return data.decode("utf-8", errors="replace")
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _get_extension(self, filename: str) -> str:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {ext}")
        return ext

    def _extract_pdf_text(self, data: bytes) -> str:
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            return "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()

    def _parse_pdf(self, data: bytes) -> str:
        text = self._extract_pdf_text(data)
        # a scanned (image-only) PDF extracts nothing — fail loudly instead of
        # letting the structurer "find" zero scenes with no explanation
        if len("".join(text.split())) < 40:
            raise ValueError("This PDF has no selectable text. It looks "
                             "scanned. Export a text PDF or upload DOCX/TXT.")
        return text

    def _parse_docx(self, data: bytes) -> str:
        doc = Document(io.BytesIO(data))
        return "\n".join(para.text for para in doc.paragraphs)
