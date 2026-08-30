from .json_loader import load_career_skill_matrix


_default_matrix = load_career_skill_matrix()

def build_route3_skill_profile(career, evaluation_results, matrix = _default_matrix):
    required_skills = matrix[career]["required_skills"]
    skills_by_id = {r["skill_id"]: r for r in evaluation_results}

    profile = []
    for skill_id, definition in required_skills.items():
        target_level = definition["target_level"]
        category = definition["category"]
        weight = definition["weight"]

        result = skills_by_id.get(skill_id)
        if result is None:
            profile.append({
                "skill_id": skill_id, "skill_name": skill_id.replace("_", " ").title(),
                "category": category, "weight": weight,
                "current_level": None, "current_level_label": "No Evidence",
                "target_level": target_level, "gap": None, "gap_label": "No Evidence",
                "priority": "None", "evidence_status": "no_evidence",
            })
            continue

        evidence_ratio = 1.0 if result["is_correct"] else 0.0
        current_level, confidence = evidence_to_skill_level(evidence_ratio, evidence_count=1)
        gap = max(target_level - current_level, 0)

        profile.append({
            "skill_id": skill_id, "skill_name": skill_id.replace("_", " ").title(),
            "category": category, "weight": weight,
            "current_level": current_level, "current_level_label": SKILL_LEVEL_LABELS[current_level],
            "target_level": target_level, "evidence_ratio": evidence_ratio,
            "gap": gap, "gap_label": gap_label(gap), "priority": priority_for_gap(gap),
            "evidence_status": "measured", "evidence_confidence": confidence,
        })

    return profile



SKILL_LEVEL_LABELS = {1: "Beginner", 2: "Novice", 3: "Intermediate", 4: "Advanced", 5: "Expert"}

def evidence_to_skill_level(evidence_ratio, evidence_count):
    if evidence_ratio >= 0.80:
        level = 5
    elif evidence_ratio >= 0.60:
        level = 4
    elif evidence_ratio >= 0.40:
        level = 3
    elif evidence_ratio >= 0.20:
        level = 2
    else:
        level = 1

    level = max(1, min(5, level))

    if evidence_count <= 1:
        level = min(level, 3)
        confidence = "low"
    elif evidence_count == 2:
        level = min(level, 4)
        confidence = "moderate"
    else:
        confidence = "high"

    return level, confidence

def gap_label(gap):
    if gap == 0:
        return "No Gap"
    if gap == 1:
        return "Low Gap"
    if gap == 2:
        return "Moderate Gap"
    return "High Gap"

def priority_for_gap(gap):
    if gap >= 3:
        return "High"
    if gap == 2:
        return "Medium"
    if gap == 1:
        return "Low"
    return "None"