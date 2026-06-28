import io
import fitz  # PyMuPDF
from docx import Document


class ScriptParser:
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

    def parse_bytes(self, data: bytes, filename: str) -> str:
        ext = self._get_extension(filename)
        if ext == ".pdf":
            return self._parse_pdf(data)
        elif ext in (".docx", ".doc"):
            return self._parse_docx(data)
        elif ext == ".txt":
            return data.decode("utf-8", errors="replace")
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _get_extension(self, filename: str) -> str:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {ext}")
        return ext

    def _parse_pdf(self, data: bytes) -> str:
        doc = fitz.open(stream=data, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)

    def _parse_docx(self, data: bytes) -> str:
        doc = Document(io.BytesIO(data))
        return "\n".join(para.text for para in doc.paragraphs)
