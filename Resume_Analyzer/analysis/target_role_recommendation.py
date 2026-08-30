from .weights_loader import load_field_skill_weights
from .skill_scoring import score_skills
from .skill_scoring import normalize_score


def recommend_target_role(categorized_skills):
    role_weights = load_field_skill_weights()
    scores = {}
    for fields in role_weights:
        
        raw_score = score_skills(categorized_skills, role_weights[fields]["categories"])
        normalized_score = normalize_score(raw_score, bucket_max = 100, k = 14.12)
        

        primary_category = role_weights[fields].get("primary_fields")
        if primary_category and not categorized_skills.get(primary_category):
            normalized_score *= role_weights[fields].get("gate_penalty", 1.0)
        scores.update({fields : normalized_score})

    return scores
    