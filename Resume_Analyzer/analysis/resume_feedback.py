from .weights_loader import load_weights_profile

def generate_strengths(extracted_info, score_result, skill_frequency, profile):
    strengths = []
    breakdown = score_result["breakdown"]
    weights = load_weights_profile(profile)
    
    # Section-level strengths: any bucket scoring high relative to its max
    bucket_maxes = {"skills": weights["skills"]["bucket_max"], "practical_experience": weights["experience_leadership"]["bucket_max"], "projects": weights["projects"]["bucket_max"], "additional_skills": weights["additional_skills"]["bucket_max"]}  # match active profile
    
    for bucket, raw_score in breakdown.items():
        if bucket == "certifications_bonus":
            continue
        pct = raw_score / bucket_maxes.get(bucket)
        if pct >= 0.75:
            strengths.append(f"Strong {bucket.replace('_', ' ')}")

    # Leadership presence (per your earlier decision to flag it explicitly)
    if extracted_info.get("leadership"):
        strengths.append("Leadership experience")

    # Skill mastery tiers, from frequency counts (your original section 5 idea)
    for skill, count in skill_frequency.items():
        if count >= 4:
            strengths.append(f"Strong grasp of {skill} (used across {count} entries)")
        elif count == 3:
            strengths.append(f"Solid experience with {skill}")

    return strengths

def generate_weaknesses(extracted_info, score_result, missing_info, profile):
    weaknesses = []
    breakdown = score_result["breakdown"]
    weights = load_weights_profile(profile)
    bucket_maxes = {"skills": weights["skills"]["bucket_max"], "practical_experience": weights["experience_leadership"]["bucket_max"], "projects": weights["projects"]["bucket_max"], "additional_skills": weights["additional_skills"]["bucket_max"]}

    for key in missing_info:
        weaknesses.append(f"Missing or incomplete: {key}")

    for bucket, raw_score in breakdown.items():
        if bucket == "certifications_bonus":
            continue
        pct = raw_score / bucket_maxes.get(bucket)
        if pct < 0.35:
            weaknesses.append(f"Weak {bucket.replace('_', ' ')}")

    soft_skills = extracted_info["skills"].get("soft_skills", [])
    if len(soft_skills) == 0:
        weaknesses.append("No soft skills listed")
    if len(soft_skills) > 0 and len(soft_skills) <= 2:
        weaknesses.append("Few soft skills listed")

    return weaknesses

def resume_feedback(extracted_info, score_result, skill_frequency, missing_info, profile):
    feedback = {
        "strengths": [],
        "weaknesses": []
    }
    feedback["strengths"] = generate_strengths(extracted_info, score_result, skill_frequency, profile)
    feedback["weaknesses"] = generate_weaknesses(extracted_info, score_result, missing_info, profile)
    return feedback