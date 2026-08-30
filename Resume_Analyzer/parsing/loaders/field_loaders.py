import json
from pathlib import Path

def load_degree_keywords_list():
    data_path = Path(__file__).parent.parent.parent / "data" / "degree_keywords.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["degree"]

def load_education_field_dict():
    data_path = Path(__file__).parent.parent.parent / "data" / "education_field_headers.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["education_field_headers"]

def load_institution_keywords_list():
    data_path = Path(__file__).parent.parent.parent/ "data" / "institution_keywords.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["institution"]

def load_months_list():
    data_path = Path(__file__).parent.parent.parent / "data" / "months_list.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["months"]

def load_segment_headers_dict():
    data_path = Path(__file__).parent.parent.parent / "data" / "segment_headers.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["section_headers"]

def load_certification_keywords_list():
    data_path = Path(__file__).parent.parent.parent/ "data" / "certification_keywords.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["certification"]

def load_job_title_keywords_list():
    data_path = Path(__file__).parent.parent.parent/ "data" / "job_title_keywords.json"
    with open(data_path, "r") as f:
        data = json.load(f)
    return data["job_titles"]
