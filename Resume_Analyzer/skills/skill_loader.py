import json
from pathlib import Path

def load_skill_list():
    data_path = Path(__file__).parent.parent / "data" / "skill_categories.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["skills"]


def load_cannonical_skill_terms_dict():
    data_path = Path(__file__).parent.parent / "data" / "cannonical_skill_terms.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["cannonical_terms"]


def load_stack_expansions_dict():
    data_path = Path(__file__).parent.parent / "data" / "skill_categories.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["stack_expansions"]