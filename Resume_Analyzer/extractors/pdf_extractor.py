# import pymupdf
# import os

# def extract_text_from_pdf(filename):
#     if not os.path.isfile(filename):
#         raise FileNotFoundError(f"Invalid path: {filename}")
#     file_list = []
#     doc = pymupdf.open(filename) 
#     for page in doc: 
#         text = page.get_text() 
#         file_list.append(text)

#     result = "\n".join(file_list)
#     if not result or result.isspace():
#         raise ValueError("PDF doesn't contain extractable text")
#     return result

import pymupdf
import os


def extract_text_from_pdf(filename):
    print(f"[PDF DEBUG] Path: {filename}")
    print(f"[PDF DEBUG] Exists: {os.path.isfile(filename)}")
    print(f"[PDF DEBUG] Size: {os.path.getsize(filename) if os.path.isfile(filename) else 'N/A'} bytes")

    if not os.path.isfile(filename):
        raise FileNotFoundError(f"Invalid path: {filename}")

    doc = pymupdf.open(filename)

    print(f"[PDF DEBUG] Pages: {len(doc)}")

    file_list = []

    for page_number, page in enumerate(doc):
        text = page.get_text()
        print(f"[PDF DEBUG] Page {page_number + 1}: {len(text)} characters")
        file_list.append(text)

    result = "\n".join(file_list)

    print(f"[PDF DEBUG] Total extracted characters: {len(result)}")
    print(f"[PDF DEBUG] First 200 chars: {repr(result[:200])}")

    if not result or result.isspace():
        raise ValueError("PDF doesn't contain extractable text")

    return result