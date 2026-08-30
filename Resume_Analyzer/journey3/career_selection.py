FIELD_TO_CAREER_KEY = {
    "Development": "development",
    "AI and Machine Learning": "ai",
    "UI/UX": "ui_ux",
    "Data Analysis": "data",
    "CyberSecurity": "cyber",
}

def select_target_career(field_scores):
    top_field = max(field_scores, key=field_scores.get)
    return FIELD_TO_CAREER_KEY[top_field]