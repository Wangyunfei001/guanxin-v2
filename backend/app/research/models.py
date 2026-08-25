"""Typed contracts shared by the Research planner and provider."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlannedToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ResearchQuestionPlan(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    tool_calls: list[PlannedToolCall] = Field(default_factory=list, max_length=4)


class ResearchPlan(BaseModel):
    summary: str = Field(default="", max_length=1000)
    questions: list[ResearchQuestionPlan] = Field(min_length=1, max_length=8)


class EvidenceGapPlan(BaseModel):
    sufficient: bool = False
    gaps: list[str] = Field(default_factory=list, max_length=8)


class ResearchSource(BaseModel):
    url: str
    title: str = ""
    publisher: str = ""
    snippet: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    text: str = ""
    sources: list[ResearchSource] = Field(default_factory=list)
    search_actions: int = 0
    raw_items: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
