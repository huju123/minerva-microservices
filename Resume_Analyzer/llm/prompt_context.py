def summarize_skill_profile(skill_profile):
    strengths = [
        s["skill_name"] for s in skill_profile
        if s.get("current_level") is not None and s["current_level"] >= s["target_level"]
    ]
    gaps = sorted(
        [s for s in skill_profile if s.get("gap")],
        key=lambda s: -s["gap"]
    )
    gap_summaries = [
        f"{s['skill_name']} (current: {s['current_level_label']}, target: level {s['target_level']}, priority: {s['priority']})"
        for s in gaps
    ]
    return strengths, gap_summaries