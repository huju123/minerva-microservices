from .loaders.field_loaders import load_segment_headers_dict

section_headers = load_segment_headers_dict()

def segment_resume(text, headers = section_headers):
    result = {"info" :[]}
    current_segment = "info"
    split_text = text.split("\n")
    for line in split_text:
        section = detect_section_header(line, headers)
        if section:
            current_segment = section
            result.setdefault(current_segment, [])
        else:
            result[current_segment].append(line)
    return result

def detect_section_header(line, headers):
    normalized = line.strip().lower()
    for section_name, variants in headers.items():
        for variant in variants:
            if  (normalized == variant and (line.isupper() or not line.islower())):
                return section_name
                                    
    return None