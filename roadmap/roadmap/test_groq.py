from planner import call_groq

result = call_groq([
    {"role": "user", "content": 'Reply with valid JSON only: {"status": "ok"}'}
])

print(result)