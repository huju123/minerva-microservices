def analyze_ats_compatibility(extracted_info, missing_info):
    issues = []
    score = 100

    if extracted_info.get("metadata", []).get("used_fallback_extraction"):
        issues.append("Resume formatting (e.g. text boxes) may not parse correctly in automated systems")
        score -= 20

    if not extracted_info["personal_info"].get("email"):
        issues.append("Email not clearly detectable")
        score -= 20

    if not extracted_info["personal_info"].get("phone_no"):
        issues.append("Phone number not clearly detectable")
        score -= 15

    core_sections = ["skills", "education", "experience"]
    for section in core_sections:
        if section in missing_info or not extracted_info.get(section):
            issues.append(f"{section.capitalize()} section not clearly identified")
            score -= 15

    score = max(score, 0)
    return {"ats_score": score, "issues": issues}