"""
Onboarding reflector — LLM call #2.

Two functions:

generate_gap_question  — makes the pre-computed gap question conversational,
                         personalised to what the agent already knows.
                         Called when completeness < 0.7.
                         Token budget: 400 context, 200 output.

generate_completion_summary — warm summary when completeness >= 0.7.
                              Token budget: 400 context, 300 output.

Both support async streaming (used by the POST /onboarding/message SSE path)
and sync one-shot generation (used by tests and the non-streaming path).
"""
from __future__ import annotations

import anthropic

from app.core.config import settings

_GAP_SYSTEM = (
    "You are a warm, friendly onboarding agent for a local marketplace. "
    "Your job is to ask one question at a time to learn about the user. "
    "Use the user's name if you know it. Keep the question natural and brief. "
    "Return only the question — no explanation, no preamble."
)

_SUMMARY_SYSTEM = (
    "You are a warm, friendly onboarding agent for a local marketplace. "
    "Generate a brief, warm completion message that summarises what you learned. "
    "Format loosely: 'Got it [name]! You're in [neighbourhood], [lifestyle detail]. "
    "You're into [style preferences] and your usual budget for furniture is around "
    "[budget range]. I'll use all of this to make your searches much faster — "
    "you'll rarely need to answer the same question twice.' "
    "Adapt naturally to whichever fields are actually set. "
    "Return only the message — no explanation."
)


def generate_gap_question(gap_field: str, default_question: str, persona: dict) -> str:
    """
    Sync — generate a conversational gap question. Falls back to the default
    question text if the LLM call fails.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    name = persona.get("identity", {}).get("display_name", "")
    try:
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=200,
            system=_GAP_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Current persona: {persona}\n"
                        f"Field needed: {gap_field}\n"
                        f"Default question: {default_question}\n"
                        f"{'User name: ' + name if name else ''}\n\n"
                        "Generate a natural, warm version of this question:"
                    ),
                }
            ],
        )
        return response.content[0].text.strip()
    except Exception:
        return default_question


def generate_completion_summary(persona: dict) -> str:
    """
    Sync — generate warm completion summary. Falls back to a generic message
    if the LLM call fails.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    name = persona.get("identity", {}).get("display_name", "")
    try:
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=300,
            system=_SUMMARY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Generate completion summary for persona:\n{persona}",
                }
            ],
        )
        return response.content[0].text.strip()
    except Exception:
        greeting = f"Got it{', ' + name if name else ''}!"
        return (
            f"{greeting} I've saved your profile. "
            "I'll use everything I've learned to make your searches much faster — "
            "you'll rarely need to answer the same question twice."
        )


async def stream_gap_question(
    gap_field: str, default_question: str, persona: dict
):
    """
    Async generator — streams the gap question token by token.
    Yields plain text chunks. Caller wraps in SSE format.
    Falls back to yielding the default_question as a single chunk on error.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    name = persona.get("identity", {}).get("display_name", "")
    try:
        async with client.messages.stream(
            model=settings.llm_model,
            max_tokens=200,
            system=_GAP_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Current persona: {persona}\n"
                        f"Field needed: {gap_field}\n"
                        f"Default question: {default_question}\n"
                        f"{'User name: ' + name if name else ''}\n\n"
                        "Generate a natural, warm version of this question:"
                    ),
                }
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text
    except Exception:
        yield default_question


async def stream_completion_summary(persona: dict):
    """
    Async generator — streams the completion summary token by token.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    name = persona.get("identity", {}).get("display_name", "")
    try:
        async with client.messages.stream(
            model=settings.llm_model,
            max_tokens=300,
            system=_SUMMARY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Generate completion summary for persona:\n{persona}",
                }
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text
    except Exception:
        greeting = f"Got it{', ' + name if name else ''}!"
        yield (
            f"{greeting} I've saved your profile. "
            "I'll use all of this to make your searches much faster."
        )
