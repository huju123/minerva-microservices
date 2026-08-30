from .fetch_missing_info import check_missing_info
from .skill_scoring import calculate_resume_score
from .skill_scoring import skill_frequency_count
from .resume_feedback import resume_feedback
from .ats_analysis import analyze_ats_compatibility
from .target_role_recommendation import recommend_target_role

def analyze_resume(extracted_info, profile):
    missing_info = check_missing_info(extracted_info)
    resume_score = calculate_resume_score(extracted_info, profile)
    skill_frequency = skill_frequency_count(extracted_info)
    str_weak = resume_feedback(extracted_info, resume_score, skill_frequency, missing_info, profile)
    ats_result = analyze_ats_compatibility(extracted_info, missing_info)
    roles_scores = recommend_target_role(extracted_info["skills"])
    return {
        "skills": extracted_info["skills"],
        "missing_info": missing_info,
        "resume_score": resume_score,
        "skill_frequency": skill_frequency,
        "strengths": str_weak["strengths"],
        "weaknesses": str_weak["weaknesses"],
        "ats_analysis": ats_result,
        "field_scores" : roles_scores
    }
    
