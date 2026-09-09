"""Typed contracts shared by the Research planner and provider."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchSource(BaseModel):
    url: str
    title: str = ""
    publisher: str = ""
    snippet: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    model: str = ""
    text: str = ""
    sources: list[ResearchSource] = Field(default_factory=list)
    search_actions: int = 0
    raw_items: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
