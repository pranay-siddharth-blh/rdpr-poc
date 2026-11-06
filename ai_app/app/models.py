"""Pydantic models for the one structured LLM call and the API bodies."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChartSpec(BaseModel):
    """The model names its own SELECT aliases; the chart data is built from the real result afterwards."""
    type: Literal["bar", "line"]
    label_column: str
    value_column: str
    series_label: str = ""


class LLMQueryPlan(BaseModel):
    answerable: bool = Field(description="False if the question can't be answered correctly from this data.")
    sql: str = Field(default="", description="One read-only SQLite SELECT over mart_* views, every column aliased.")
    answer_template: str = Field(default="", description="Answer sentence with {alias} placeholders.")
    clarification_message: str = Field(default="", description="Only when answerable is false.")
    chart_data: ChartSpec | None = None


class AskRequest(BaseModel):
    question: str = Field(max_length=4000)
    # "voice": the response also carries spoken_answer (what the voice says). "text" is unchanged.
    mode: Literal["text", "voice"] = "text"
    # the last question the page had answered: a follow-up ("and Hassan?") is rewritten against it (app/followup.py)
    previous: str = Field(default="", max_length=4000)


class AskResponse(BaseModel):
    question: str
    answerable: bool
    answer: str
    route: str = ""
    sql: str = ""
    columns: list[str] = []
    rows: list[list] = []
    truncated: bool = False
    table: dict | None = None
    chart: dict | None = None
    notes: list[str] = []
    entities: dict = {}
    timing_ms: dict = {}
    error: str = ""
    verification: str = ""
    report_id: str = ""
    asked_as: str = ""         # a follow-up: the whole question it was answered as ("" when asked as typed)
    context: bool = False      # answered from the data: the page may send it as `previous` for a follow-up
    spoken_answer: str = ""    # voice mode only: 1-2 sentences built from the answer (app/spoken.py), no model call
