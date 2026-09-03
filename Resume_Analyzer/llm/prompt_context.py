LEVEL_LABELS = {
    1: "Beginner",
    2: "Novice",
    3: "Intermediate",
    4: "Advanced",
    5: "Expert"
}


def summarize_skill_profile(adapted_profile):
    """
    Summarize the student's skill profile.

    Supports both formats:

    1. Direct list:
       [
           {
               "skill_id": "analytical_reasoning",
               "current_level": 3,
               "target_level": 4,
               "gap": 1,
               "priority": "Low"
           }
       ]

    2. Dictionary containing a skills list:
       {
           "skills": [
               {
                   "skill_id": "analytical_reasoning",
                   "current_level": 3,
                   "target_level": 4,
                   "gap": 1,
                   "priority": "Low"
               }
           ]
       }
    """

    if not adapted_profile:
        return [], []

    # Case 1: skill_profile is directly a list
    if isinstance(adapted_profile, list):
        skills = adapted_profile

    # Case 2: skill_profile is {"skills": [...]}
    elif isinstance(adapted_profile, dict):
        skills = adapted_profile.get("skills", [])

    # Unsupported format
    else:
        return [], []

    strengths = []
    gap_items = []

    for s in skills:
        skill_id = s.get("skill_id")

        if not skill_id:
            continue

        skill_name = skill_id.replace("_", " ").title()

        current = s.get("current_level")
        target = s.get("target_level")
        gap = s.get("gap")
        priority = s.get("priority")

        # Student already meets or exceeds the target level
        if (
            current is not None
            and target is not None
            and current >= target
        ):
            strengths.append(skill_name)

        # Student has a skill gap
        elif gap:
            level_label = LEVEL_LABELS.get(current, "No Evidence")

            gap_items.append(
                (
                    gap,
                    f"{skill_name} "
                    f"(current: {level_label}, "
                    f"target: level {target}, "
                    f"priority: {priority})"
                )
            )

    # Highest skill gaps first
    gap_items.sort(key=lambda x: -x[0])

    return strengths, [text for _, text in gap_items]