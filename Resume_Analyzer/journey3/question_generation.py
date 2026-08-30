from ..llm.client import get_llm_response
from ..llm.client import normalize_llm_text
import random

def select_target_skills(career, matrix, num_core=4, num_supporting=1):
    required = matrix[career]["required_skills"]
    core = [sid for sid, s in required.items() if s["category"] == "core"]
    supporting = [sid for sid, s in required.items() if s["category"] == "supporting"]
    # return core[:num_core] + supporting[:num_supporting]
    return random.sample(core, min(num_core, len(core))) + random.sample(supporting, min(num_supporting, len(supporting)))

def generate_route3_questions(career, extracted_info, matrix):
    target_skill_ids = select_target_skills(career, matrix)
    all_skills = [skill for category in extracted_info["skills"].values() for skill in category]

    questions = []
    for skill_id in target_skill_ids:
        readable_skill = skill_id.replace('_', ' ')
        system_prompt = f"""You are a technical interviewer assessing a computer science student's competency in "{readable_skill}".

This student's known technical background (from their resume): {all_skills}

Generate ONE focused interview question that tests a SINGLE, specific aspect of {readable_skill} —
not multiple sub-parts. The question should be answerable by a CS undergraduate with solid fundamentals; avoid requiring memorized advanced algorithms or highly specialized techniques; focus on testing whether the underlying concept is understood. 
The question should have one clear correct concept or approach a competent
student would name, so that a rater could later judge the answer as correct or incorrect, not
partially correct. Where possible, phrase it using a scenario relevant to the student's known
background above.

Respond with ONLY the question text, nothing else."""
        question_text = get_llm_response(system_prompt, "Generate the question now.")
        text = normalize_llm_text(question_text)
        questions.append({"skill_id": skill_id, "question": text})

    return questions
