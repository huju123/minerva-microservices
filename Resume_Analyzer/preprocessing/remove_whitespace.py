import re

def normalize_whitespace(text):
    result = []
    tab_pattern = "[ \t]{2,}"
    newline_pattern = "\n{3,}"
    text = re.sub(tab_pattern, " ", text)
    text = re.sub(newline_pattern, "\n\n", text)
    output = text.split("\n")
    for line in output:
        cl_text = line.strip()
        result.append(cl_text)
    result_text = "\n".join(result)
    result_text = result_text.strip()
    return result_text
        

