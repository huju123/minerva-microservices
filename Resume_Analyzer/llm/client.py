def get_llm_judgment(prompt: str) -> str:
    """
    Placeholder for LLM API calls (scoring nuance, chatbot, interview evaluation).
    Swap the body of this function for a real API call once you have access —
    every caller in the codebase stays unchanged.
    """
    return "[stubbed response — replace with real API call]"

# def get_llm_response(system_prompt: str, user_message: str, conversation_history: list = None) -> str:
#     """
#     Sends a prompt to an LLM and returns its text response.

#     STUB VERSION: returns a fixed placeholder so the rest of the app
#     can be built and tested without real API access.

#     Real version (later): replace the body with an actual API call
#     to whichever provider you land on (Gemini, OpenAI, Anthropic, etc.),
#     using system_prompt + conversation_history + user_message to build
#     the request, and returning just the text of the response.
#     """
#     return f"[STUBBED LLM RESPONSE] Would respond to: '{user_message}'"

import os
from groq import Groq
from dotenv import load_dotenv
import json

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_llm_response(system_prompt: str, user_message: str, conversation_history: list = None) -> str:
    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=messages,
    )
    return response.choices[0].message.content


def get_structured_llm_response(system_prompt, user_message, conversation_history=None, retries=1):
    for attempt in range(retries + 1):
        raw = get_llm_response(system_prompt, user_message, conversation_history)
        text = normalize_llm_text(raw)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if attempt == retries:
                raise ValueError(f"LLM did not return valid JSON after {retries + 1} attempt(s): {raw[:200]}")


def normalize_llm_text(text):
    text = text.replace("\u202f", " ")   # narrow no-break space
    text = text.replace("\u00a0", " ")   # regular no-break space, another common offender
    return text