from .pdf_extractor import extract_text_from_pdf
from .docx_extractor import extract_text_from_docx
from pathlib import Path

def file_format_router(filename):
    suffex = Path(filename).suffix
    if suffex.lower() == ".pdf":
        result = extract_text_from_pdf(filename)
        return result, False
    elif suffex.lower() == ".docx":
        result, used_fallback = extract_text_from_docx(filename)
        return result, used_fallback
    else:
        raise ValueError(f"Unsupported File Format: {suffex}")
        