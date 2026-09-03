from .client import get_structured_llm_response
from .client import normalize_llm_text
from.prompt_context import summarize_skill_profile

def generate_interview_questions(target_role, skill_profile, num_questions=5):
    try:
        strengths, gap_summaries = summarize_skill_profile(skill_profile)

        system_prompt = f"""
        You are a hiring manager for {target_role} role gauging
        computer science students whether they are suited for {target_role} roles.

        To do this, generate {num_questions} interview
        questions for {target_role}, tailored using the student's skill assessment results.

        Here is the student's skill assessment:
        - Strengths (meeting or exceeding target level) = {strengths}
        - Skill gaps (ordered by priority) = {gap_summaries}

        Use only this information to tailor interview
        questions. The questions can be Multiple choice based, One to two line answers or a short problem.

        Respond with ONLY a valid JSON array of strings, and
        nothing else - no explanation, no markdown code fences, no extra text.

        Example format: ["question 1", "question 2", "question 3"]
        """

        response = get_structured_llm_response(
            system_prompt,
            "Generate the questions now."
        )

        return {
            "success": True,
            "data": response
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def evaluate_interview_answers(question, student_answer, target_role):
    try:
        system_prompt = f"""
        You are a hiring manager for {target_role} roles
        evaluating computer science students.

        The student was asked the following interview questions:
        "{question}"

        Evaluate their answers.

        Respond with a score out of 10 for ALL answers combined
        and 2-3 sentences of feedback per question.

        Respond with ONLY valid JSON and nothing else.
        No explanation.
        No markdown code fences.
        No extra text.

        Example format:
        {{"scores": [1, 2, 3], "total": 6, "feedback": ["...", "...", "..."]}}
        """

        response = get_structured_llm_response(
            system_prompt,
            student_answer
        )

        return {
            "success": True,
            "data": response
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

        
    
    