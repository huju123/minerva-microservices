from .client import get_llm_response
from .client import normalize_llm_text
from.prompt_context import summarize_skill_profile


def build_chatbot_system_prompt(adapted_profile=None, career=None):
    if adapted_profile:
        strengths, gap_summaries = summarize_skill_profile(adapted_profile)
        career_line = f"Target career: {career}\n" if career else ""
        skill_context = f'''{career_line}Here is the student's skill assessment:
- Strengths (meeting or exceeding target level) = {strengths}
- Skill gaps (ordered by priority) = {gap_summaries}

Answer the student's question using this information when relevant.'''
    else:
        skill_context = "This student has not completed a skill assessment yet. Answer generally, and if their question depends on personal skill data you don't have, suggest they complete an assessment first."

    return f'''You are a career advisor for Minerva, an AI-powered career growth platform for computer science students.

{skill_context}

Be specific and concrete rather than generic. Keep your response conversational — 3-5 sentences, no tables, no numbered action plans.'''


def handle_chat_message(user_message, adapted_profile=None, conversation_history=None, career=None):
    try:
        if conversation_history is None:
            conversation_history = []
        system_prompt = build_chatbot_system_prompt(adapted_profile, career)
        response = get_llm_response(system_prompt, user_message, conversation_history)
        text = normalize_llm_text(response)
        updated_history = conversation_history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": text}
        ]
        return {"success": True, "data": {"response": text, "updated_history": updated_history}}
    except Exception as e:
        return {"success": False, "error": str(e)}