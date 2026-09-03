
LEVEL_LABELS = {1: "Beginner", 2: "Novice", 3: "Intermediate", 4: "Advanced", 5: "Expert"}

def summarize_skill_profile(adapted_profile):
    if not adapted_profile or not adapted_profile.get("skills"):
        return [], []

    skills = adapted_profile["skills"]
    strengths = []
    gap_items = []

    for s in skills:
        skill_name = s["skill_id"].replace("_", " ").title()
        current, target = s.get("current_level"), s.get("target_level")

        if current is not None and target is not None and current >= target:
            strengths.append(skill_name)
        elif s.get("gap"):
            level_label = LEVEL_LABELS.get(current, "No Evidence")
            gap_items.append((s["gap"], f"{skill_name} (current: {level_label}, target: level {target}, priority: {s.get('priority')})"))

    gap_items.sort(key=lambda x: -x[0])
    return strengths, [text for _, text in gap_items]