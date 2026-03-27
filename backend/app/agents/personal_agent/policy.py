from __future__ import annotations


def is_memory_question(content: str) -> bool:
    lowered = content.lower()
    return any(
        token in lowered
        for token in [
            "what do you remember",
            "what do you know about me",
            "remember about me",
            "my preferences",
        ]
    )


def is_mandate_request(content: str) -> bool:
    lowered = content.lower()
    return any(
        token in lowered
        for token in [
            "buy",
            "sell",
            "find me",
            "under $",
            "budget",
            "listing",
            "marketplace",
        ]
    )


def mandate_deflection_message() -> str:
    return (
        "I’m your Personal Agent for profile and preferences only. "
        "For active buying/selling requests, please switch to the Mandate Agent."
    )
