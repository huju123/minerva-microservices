import json

from level_rules import apply_profile_level_rules
from retrieval import load_resources, retrieve_profile
from planner import plan_from_profile

resources = load_resources()

profile = {
    "journey": "career-in-mind",
    "career": "development",
    "target_role": None,
    "current_experience_level": None,
    "goal": "Become job-ready as a Developer",
    "weekly_hours": None,
    "skills": [
        {
            "skill_id": "python",
            "current_level": 1,
            "target_level": 3,
            "gap": 2,
            "gap_label": "Moderate Gap",
            "priority": "Critical",
            "category": "core",
            "weight": 1.0,
            "confidence": 0.75,
            "evidence_status": "measured",
        },
    ],
    "strengths": [],
    "weak_areas": [],
    "preferences": {},
}

plan = plan_from_profile(profile, resources=resources, use_model=True)

print("SOURCE:", plan["_source"])
print(json.dumps(plan, indent=2))