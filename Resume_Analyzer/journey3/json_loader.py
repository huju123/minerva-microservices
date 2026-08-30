import json
from pathlib import Path

def load_career_skill_matrix():
    data_path = Path(__file__).parent.parent / "data" / "career_skill_matrix.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["careers"]