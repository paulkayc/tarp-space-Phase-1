from __future__ import annotations


def enforce_one_question(text: str) -> str:
    question_marks = text.count("?")
    if question_marks <= 1:
        return text
    first = text.split("?")[0].strip()
    return f"{first}?"
