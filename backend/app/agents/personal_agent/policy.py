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


def one_question_guard(text: str) -> str:
    question_marks = text.count("?")
    if question_marks <= 1:
        return text
    head, *_ = text.split("?")
    return f"{head.strip()}?"
