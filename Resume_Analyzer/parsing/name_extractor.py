from ..contact_extractor.email_extractor import extract_email
from ..contact_extractor.phone_extractor import extract_phone_no

def extract_name(header_lines):
    url_keywords = ["github", "linkedin", "www", "http"]
    for line in header_lines:
        flag = False
        normalize = line.strip()
        if not normalize:
            continue
        for each in url_keywords:
            if each in normalize:
                flag = True
        flag = flag or extract_email(normalize) or extract_phone_no(normalize)
        if not flag:
            return normalize
        
    
