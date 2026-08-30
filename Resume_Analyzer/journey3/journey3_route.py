from ..resume_extraction import extract_resume
from ..analysis.resume_analysis import analyze_resume
from .career_selection import select_target_career
from .json_loader import load_career_skill_matrix
from .question_generation import generate_route3_questions
from .answer_evaluation import evaluate_route3_answer
from .skill_profile_engine import build_route3_skill_profile


def run_route3_assessment(filepath, profile = "internship"):

    try:
        extracted_info = extract_resume(filepath)
        analysis_result = analyze_resume(extracted_info, profile)
    
        matrix = load_career_skill_matrix()
        target_role = select_target_career(analysis_result["field_scores"])
        questions = generate_route3_questions(target_role, analysis_result, matrix)
        return {
        "success" : True,
        "data" : {
            "career": target_role,
            "questions": questions,
            "analysis_result": analysis_result
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    
        

def evaluate_route3_assessment(questions, answers, career):
    try:
        if len(questions) != len(answers):
            raise ValueError(f"Expected {len(questions)} answers, got {len(answers)}")

        evaluation_results = []
        for q, answer in zip(questions, answers):
            feedback = evaluate_route3_answer(q["question"], answer, q["skill_id"])
            evaluation_results.append({
                "skill_id": q["skill_id"],
                "is_correct": feedback["is_correct"],
                "reasoning": feedback["reasoning"]
            })
    
        skill_profile = build_route3_skill_profile(career, evaluation_results)
    
        return {
            "success" : True,
            "data": {
                "evaluation_results": evaluation_results,
                "skill_profile" : skill_profile
                }
            }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


