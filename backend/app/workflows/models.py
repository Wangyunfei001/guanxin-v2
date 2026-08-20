"""Typed contracts for workflow planning and execution."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


STEP_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class WorkflowPlanStep(BaseModel):
    step_id: str
    title: str = Field(min_length=1, max_length=120)
    tool_name: str = Field(min_length=1, max_length=160)
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("step_id")
    @classmethod
    def valid_step_id(cls, value: str) -> str:
        if not STEP_ID_PATTERN.fullmatch(value):
            raise ValueError("step_id 只能包含字母、数字、下划线和连字符")
        return value


class WorkflowPlan(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=1000)
    steps: list[WorkflowPlanStep] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_step_ids(self) -> "WorkflowPlan":
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id 必须唯一")
        return self


class ToolParameter(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    options: list[Any] = Field(default_factory=list)


class WorkflowTool(BaseModel):
    name: str
    display_name: str
    description: str
    category: str
    risk: str
    parameters: list[ToolParameter] = Field(default_factory=list)
