from .weights_loader import load_score_weights
from .weights_loader import load_weights_profile
from parsing.loaders.field_loaders import load_months_list
from parsing.experience_extractor import extract_experience
from skills.extract_skills import find_skills_overlap_safe
from collections import Counter
import re

category_weights = load_score_weights()

months = load_months_list()
month_alternatives = "|".join(months)

single_point = r"(?:(?:" + month_alternatives + r")\.?\s*\d{4}|\d{4})"
exp_date_pattern = r"\s*"+single_point+r"\s*-\s*(?:"+single_point+r"|Present)"

projects_date_pattern = r"(?:(?:" + month_alternatives + r")\.?\s*\d{4}|\d{4})"

def score_skills(categorized_skills, weights = category_weights):
    score = 0
    for category in categorized_skills.keys():
        length = len(categorized_skills[category])
        full_weight = weights[category].get("weight")
        if weights[category].get("threshold"):
            threshold = weights[category].get("threshold")
            reduced_weight = full_weight * weights[category].get("padding_fraction")
            score = score + (min(length, threshold) * full_weight + max(0, length - threshold) * reduced_weight)
            # print(f"length = {length} | weight = {full_weight} | threshold = {threshold} | reduced_weight = {reduced_weight} | score = {score}")
        else:
            score = score + (full_weight * length)
    #         print(f"length = {length} | weight = {full_weight} | score = {score}")
    # print(score)
    return score


def normalize_score(raw_score, bucket_max, k):
    return bucket_max * (raw_score / (raw_score + k))

def score_skills_normalized(categorized_skills, weights, k):
    raw = score_skills(categorized_skills)
    return normalize_score(raw, bucket_max = weights, k = k)



def score_experience_leadership(extracted_info, weights, k):
    exp_entries = len(extracted_info["experience"])
    leader_entries = len(extracted_info["leadership"])
    total_entries = exp_entries + leader_entries
    normalized_score = normalize_score(total_entries, bucket_max = weights, k = k)
    return normalized_score


def score_projects(projects, weights, k):
    project_entries = len(projects)
    normalized_score = normalize_score(project_entries, bucket_max = weights, k = k)
    # Projects score is a deterministic baseline; Layer 3, when available, applies a bounded quality adjustment on top — never replaces the base score.
    return normalized_score

def score_certifications(certifications, weights, k):
    cert_entries = len(certifications)
    normalized_score = normalize_score(cert_entries, bucket_max = weights, k = k)
    return normalized_score



def skill_frequency_count(extracted_info):
    all_entry_skill_lists = []
    for entry in extracted_info["experience"] + extracted_info["projects"] + extracted_info["leadership"]:
        description_text = "\n".join(entry["description"]) 
        matched = find_skills_overlap_safe(description_text)
        skill_list = []
        for each in matched.keys():     
            skill_list.extend(matched[each])
        if entry.get("tech_stack"):
            # print("border")
            for key in entry["tech_stack"]:
                for skill in entry["tech_stack"].get(key):
                    # print(f"skill = {skill} | category : {key}")
                    skill_list.append(skill)
        # print(skill_list)
        skill_list = set(skill_list)
        skill_list = list(skill_list)
        # print(skill_list)
        all_entry_skill_lists.append(skill_list)
    # project_tech_stacks = [skill for entry in extracted_info["projects"] for skill in entry["tech_stack"]]
    all_matches = [skill for entry_list in all_entry_skill_lists for skill in entry_list]
    # all_matches.extend(project_)
    frequency = Counter(all_matches)
    return frequency


def score_additional_skills(extracted_info, weights , k):
    skill_freq = skill_frequency_count(extracted_info)
    top_skills = extracted_info["skills"]
    top_skills_list = [skill for key in top_skills.keys() for skill in top_skills[key]]
    top_skills_set = set(top_skills_list)
    additional_skills = skill_freq.keys() - top_skills_set 
    additional_skills_length = len(additional_skills)
    normalized_score = normalize_score(additional_skills_length, bucket_max = weights, k = k)
    return normalized_score

def calculate_resume_score(extracted_info, profile = "internship"):
    weights = load_weights_profile(profile)
    skill_score = score_skills_normalized(extracted_info["skills"], weights["skills"]["bucket_max"], weights["skills"]["k"])
    exp_lead_score = score_experience_leadership(extracted_info, weights["experience_leadership"]["bucket_max"], weights["experience_leadership"]["k"])
    projects_score = score_projects(extracted_info["projects"],  weights["projects"]["bucket_max"], weights["projects"]["k"])
    # cert_score = score_certifications(extracted_info["certifications"])
    add_skills_score = score_additional_skills(extracted_info, weights["additional_skills"]["bucket_max"], weights["additional_skills"]["k"])
    base_score = skill_score + exp_lead_score + projects_score + add_skills_score

    cert_length = len(extracted_info["certifications"])
    cert_bonus = normalize_score(cert_length, bucket_max = weights["certifications"]["bucket_max"], k = weights["certifications"]["k"])

    final_score = min(base_score + cert_bonus, 100)
    return {
        "final_score": round(final_score, 2),
        "breakdown": {
            "skills": round(skill_score, 2),
            "practical_experience": round(exp_lead_score, 2),
            "projects": round(projects_score, 2),
            "additional_skills": round(add_skills_score, 2),
            "certifications_bonus": round(cert_bonus, 2),
        }
    }
    
    