import fitz
from docx import Document


SUPPORTED_EXTENSIONS = {"pdf", "docx", "txt"}


def extract_text_from_pdf(path: str) -> str:
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()


def extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text_from_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read().strip()


def extract_text(path: str, extension: str) -> str:
    if extension == "pdf":
        return extract_text_from_pdf(path)
    if extension == "docx":
        return extract_text_from_docx(path)
    if extension == "txt":
        return extract_text_from_txt(path)
    raise ValueError(f"Неподдерживаемый тип файла: {extension}")
