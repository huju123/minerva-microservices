import pymupdf
import os

def extract_text_from_pdf(filename):
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"Invalid path: {filename}")
    file_list = []
    doc = pymupdf.open(filename) 
    for page in doc: 
        text = page.get_text() 
        file_list.append(text)

    result = "\n".join(file_list)
    if not result or result.isspace():
        raise ValueError("PDF doesn't contain extractable text")
    return result