from .loaders.field_loaders import load_certification_keywords_list
from .education_extractor import extract_education_history
from .certificate_extractor import extract_certificates
import re

def classify_education_certification_lines(text):
    education = []
    certification = []
    education_certification = {
        "education": [],
        "certifcation" : []
    }
    if not text:
        return []
    for line in text:
        result = check_certification_keywords_in_lines(line)
        if result:
            certification.append(line)
        else:
            education.append(line)
            
    education_certification["education"] = extract_education_history(education) if education else []
    education_certification["certification"] = extract_certificates(certification) if certification else []
    return education_certification
    
    

def check_certification_keywords_in_lines(line):
    keywords = load_certification_keywords_list()
    for each in keywords:
        pattern = r"(?<!\w)" + re.escape(each) + r"(?!\w)"
        result = re.search(pattern, line, re.IGNORECASE)
        if result:
            return result
    return None