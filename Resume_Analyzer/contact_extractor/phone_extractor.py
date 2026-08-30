import re

def extract_phone_no(text):
    pk_pattern_post_code = r"[(+]{0,2}?[\d]{2}[-)\s]{1,2}?[\d]{3}[-\s]?[\d]{7}"
    pk_pattern_general = r"0[\d]{3}[-\s]?[\d]{7}"
    result = re.search(pk_pattern_general, text)
    if result:
        return result.group()
    result = re.search(pk_pattern_post_code, text)
    if result:
        return result.group()

    return None