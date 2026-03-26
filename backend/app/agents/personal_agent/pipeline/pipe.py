from __future__ import annotations

from typing import Any, Callable


class Pipeline:
    def __init__(self):
        self._steps: list[Callable[[dict[str, Any]], dict[str, Any]]] = []

    def add_step(self, step: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._steps.append(step)

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        current = dict(context)
        for step in self._steps:
            current = step(current)
        return current
