from .client import get_llm_response
from .client import normalize_llm_text
from.prompt_context import summarize_skill_profile

def handle_chat_message(user_message, skill_profile, conversation_history=None, career = None):
    try:
        if conversation_history is None:
            conversation_history = []
        system_prompt = build_chatbot_system_prompt(skill_profile, career)
        response = get_llm_response(system_prompt, user_message, conversation_history)
        text = normalize_llm_text(response)
    
        updated_history = conversation_history + [
            {"role" : "user", "content" : user_message},
            {"role" : "assistant", "content": text}
        ]
        return {
            "success": True,
            "data" : {
                "response" : text,
                "updated_history": updated_history
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    
def build_chatbot_system_prompt(skill_profile, career):
    strengths, gap_summaries = summarize_skill_profile(skill_profile)
    career_line = f"Target career: {career}\n" if career else ""
    return f'''You are a career advisor helping a computer science student understand their skill assessment.

{career_line}Here is the student's skill assessment:
- Strengths (meeting or exceeding target level) = {strengths}
- Skill gaps (ordered by priority) = {gap_summaries}

Answer the student's question using only this information. Be specific and reference their actual skills
and gaps rather than giving generic advice. Keep your answer concise and encouraging, but honest about
real gaps. Keep your response conversational — 3-5 sentences, no tables, no numbered action plans.'''