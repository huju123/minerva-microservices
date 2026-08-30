from llm.client import get_structured_llm_response
from llm.client import normalize_llm_text


def evaluate_route3_answer(question, student_answer, skill_id):
    readable_skill = skill_id.replace('_', ' ')
    system_prompt = f"""You are a technical interviewer evaluating a student's answer to a question testing "{readable_skill}".

Question: "{question}"

Grading criteria:
- Mark is_correct as TRUE if the student identifies the correct core concept, technique, or approach —
  even if they omit secondary details (e.g. complexity analysis, full justification), or phrase their
  answer with hedging or uncertain tone (e.g. "I think", "maybe", "not sure but").
- Mark is_correct as FALSE only if the core concept/technique itself is wrong, missing, or the answer
  is too vague to identify any correct technical content at all.
- Regardless of the true/false verdict, your reasoning must note anything the student omitted (missing
  justification, incomplete explanation) and comment on their tone/confidence if relevant, so they get
  useful feedback even when marked correct.

Respond with ONLY valid JSON, no markdown, no extra text, in this exact shape:
{{"is_correct": true or false, "reasoning": "1-2 sentences noting both correctness and what could improve"}}"""

    response = get_structured_llm_response(system_prompt, student_answer)
    # text = normalize_llm_text(response)
    return response