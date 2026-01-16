from app.services.llm.ollama_llm import OllamaLLM

def generate_summary(components: list, tech_stack: list) -> str:
    prompt = f"""
You are a software architect.

Based ONLY on this information, write a concise overview
(4–6 sentences max). Do NOT guess.
Do NOT describe LLMs as search engines.
LLMs are only used for response generation.

Components:
{components}

Tech stack:
{tech_stack}
"""
    return OllamaLLM().generate(prompt)