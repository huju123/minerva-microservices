import re

def normalize_bullets_by_line(text):
    common_bullet_point_list = ["•", "◦","‣","◉","▪","▫","■","□",  "◼","◻","▸","▹","➤","➣","–","—","✦","❖","❧","·","∙" ]
    regex_pattern = r"^[" + "".join(common_bullet_point_list) + "]\s*"
    result = re.sub(regex_pattern, "- ", text, flags=re.MULTILINE)
    return result
