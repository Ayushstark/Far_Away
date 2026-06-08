from typing import Literal

from pydantic import BaseModel, Field


AgentName = Literal[
    "symptom_analyst",
    "report_reader",
    "medication_manager",
    "care_coordinator",
    "emergency_detector",
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    profile_id: str = Field(default="demo-user", max_length=100)


class AgentResult(BaseModel):
    agent: AgentName
    summary: str


class ChatResponse(BaseModel):
    message: str
    agents_used: list[AgentName]
    results: list[AgentResult]
    emergency: bool = False
    disclaimer: str = (
        "CareOS provides general health information and does not replace a "
        "qualified medical professional."
    )
