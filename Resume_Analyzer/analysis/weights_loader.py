import json
from pathlib import Path

def load_score_weights():
    data_path = Path(__file__).parent.parent / "data" / "skill_category_weights.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["category_weights"]

def load_weights_profile(profile):
    if profile.lower() == "job":
        data_path = Path(__file__).parent.parent / "data" / "profile_weights.json"
        with open(data_path, "r") as f:
            data = json.load(f)
        return data["job_weights"]
    else:
        data_path = Path(__file__).parent.parent / "data" / "profile_weights.json"
        with open(data_path, "r") as f:
            data = json.load(f)
        return data["internship_weights"]


def load_field_skill_weights():
    data_path = Path(__file__).parent.parent / "data" / "field_category_weights.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["field_weights"]
    

