import re

def extract_email(text):
    pattern = r"[\w.+-]+@[\w+-\.]+[A-Za-z]{2,}"
    result = re.search(pattern, text)
    if result:
        return result.group()
    else:
        return None
    