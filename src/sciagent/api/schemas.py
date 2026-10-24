from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)


class StepOut(BaseModel):
    tool: str
    arguments: dict[str, Any]
    decision: str
    reason: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user: str
    question: str
    status: str
    answer: str
    steps: list[StepOut]
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    model: str
    created_at: datetime


class DatasetIn(BaseModel):
    name: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_\-]{2,99}$")
    modality: str = Field(..., pattern=r"^(imaging|genomics|clinical)$")
    group: str
    uri: str
    row_count: int = Field(0, ge=0)
    checksum: str = ""
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")
    lineage: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    name: str
    modality: str
    group: str
    uri: str
    version: int
    row_count: int
    checksum: str
    schema_: dict[str, Any] = Field(serialization_alias="schema")
    lineage: dict[str, Any]
    description: str
    created_at: datetime


class ToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    ts: datetime
    actor: str
    action: str
    resource: str
    decision: str
    details: dict[str, Any]
    hash: str


class SearchHit(BaseModel):
    id: str
    text: str
    score: float
