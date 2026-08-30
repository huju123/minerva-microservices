from preprocessing.remove_whitespace import normalize_whitespace
# from .loaders.field_loaders import load_months_list
# import re

# months = load_months_list()
# month_alternatives = "|".join(months)
# date_pattern = r"(?:(?:" + month_alternatives + r")\.?\s*\d{4}|\d{4})"

def extract_certificates(text):
    certificates = []
    for line in text:
        certificates.append(normalize_whitespace(line))
    result = list(filter(None, certificates))
    return result



# def match_date_pattern(line):
#     result = re.search(date_pattern, line)
#     if result:
#         return result
#     return None