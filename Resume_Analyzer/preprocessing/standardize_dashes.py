def normalize_dashes(text):
    dash_characters = ["–", "—", "−"]  # en dash, em dash, minus sign
    for dash in dash_characters:
        text = text.replace(dash, "-")
    return text