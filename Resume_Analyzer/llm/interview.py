from .client import get_structured_llm_response
from .client import normalize_llm_text
from.prompt_context import summarize_skill_profile

def generate_interview_questions(target_role, skill_profile, num_questions=5):
    try:
        strengths, gap_summaries = summarize_skill_profile(skill_profile)

        system_prompt = f"""
        You are a hiring manager for {target_role} role gauging
        computer science students whether they are suited for {target_role} roles.

        Generate exactly {num_questions} interview questions for {target_role},
        tailored using the student's skill assessment results.

        Strengths = {strengths}
        Skill gaps (ordered by priority) = {gap_summaries}

        Respond with ONLY a valid JSON array of objects, nothing else.
        Each object MUST have exactly these keys: "id", "question", "field".
        "id" must be "q1", "q2", "q3", ... in order.
        "field" must always be "{target_role}".

        Example format:
        [{{"id": "q1", "question": "...", "field": "{target_role}"}},
         {{"id": "q2", "question": "...", "field": "{target_role}"}}]
        """

        response = get_structured_llm_response(system_prompt, "Generate the questions now.")

        # Issue #2 fix lives right here — see below
        if not isinstance(response, list) or len(response) != num_questions:
            return {"success": False, "error": f"Expected {num_questions} questions, got {len(response) if isinstance(response, list) else 'invalid'}"}

        ids = [q.get("id") for q in response]
        if len(set(ids)) != len(ids):
            return {"success": False, "error": "Duplicate question IDs generated"}

        return {"success": True, "data": response}

    except Exception as e:
        return {"success": False, "error": str(e)}


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

        
    
    