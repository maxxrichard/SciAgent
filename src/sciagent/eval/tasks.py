from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal["imaging", "genomics", "clinical", "harmonisation", "governance", "safety"]


class NumberFromTool(BaseModel):
    """A figure the answer must contain, computed from a reference tool call."""

    tool: str
    arguments: dict[str, Any]
    field: str  # dotted path into the tool result, e.g. "groups.F.n"


class Expected(BaseModel):
    status: Literal["completed", "blocked", "max_steps"] = "completed"
    tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    answer_contains: list[str] = Field(default_factory=list)
    answer_excludes: list[str] = Field(default_factory=list)
    numbers: list[NumberFromTool] = Field(default_factory=list)


class Persona(BaseModel):
    user: str = "eval-researcher"
    role: Literal["researcher", "analyst", "admin"] = "researcher"
    groups: list[str] = Field(default_factory=lambda: ["imaging", "genomics", "clinical"])


class EvalTask(BaseModel):
    id: str
    category: Category
    question: str
    persona: Persona = Field(default_factory=Persona)
    expected: Expected = Field(default_factory=Expected)
    rubric: str = ""
    tags: list[str] = Field(default_factory=list)


def load_tasks(path: Path) -> list[EvalTask]:
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    tasks: list[EvalTask] = []
    for f in files:
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if line.strip() and not line.lstrip().startswith("//"):
                try:
                    tasks.append(EvalTask.model_validate(json.loads(line)))
                except Exception as exc:
                    raise ValueError(f"{f}:{n}: {exc}") from exc
    ids = [t.id for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")
    return tasks
