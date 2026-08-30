from .remove_whitespace import normalize_whitespace
from .standardize_bullet_points import normalize_bullets_by_line
from .standardize_dashes import normalize_dashes

def clean_text(text):
    result = normalize_whitespace(text)
    output = normalize_bullets_by_line(result)
    final = normalize_dashes(output)
    return final