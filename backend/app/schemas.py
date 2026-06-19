from typing import Any, Literal

from pydantic import BaseModel, Field


IntentName = Literal[
    "symptom_analysis",
    "report_reading",
    "medication_management",
    "care_coordination",
    "emergency_detection",
]
AgentName = Literal[
    "symptom_analyst",
    "report_reader",
    "medication_manager",
    "care_coordinator",
    "emergency_detector",
]
MedicationAction = Literal["add", "check_interactions", "explain", "list"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    profile_id: str = Field(default="9000001", max_length=100)
    family_member_id: str | None = Field(default=None, max_length=100)
    preferred_language: Literal["en", "hi"] = "en"
    previous_assistant_message: str | None = Field(default=None, max_length=10_000)
    conversation_history: list[str] = Field(default_factory=list, max_length=12)
    follow_up_event_id: str | None = Field(default=None, max_length=100)


class AgentResult(BaseModel):
    agent: AgentName
    summary: str


class EmergencyAssessment(BaseModel):
    is_emergency: bool = False
    severity: Literal["critical", "moderate", "none"] = "none"
    suspected: str = ""
    immediate_steps: list[str] = Field(default_factory=list)
    call_number: str = "112 or 108"
    family_notified: bool = False


class ChatResponse(BaseModel):
    message: str
    intents: list[IntentName] = Field(default_factory=list)
    agents_used: list[AgentName]
    steps_taken: list[str] = Field(default_factory=list)
    results: list[AgentResult]
    severity: Literal["high", "moderate", "none"] = "none"
    follow_up_outcome: Literal["resolved", "ongoing"] | None = None
    emergency: bool = False
    emergency_details: EmergencyAssessment | None = None
    disclaimer: str = (
        "CareOS provides general health information and does not replace a "
        "qualified medical professional."
    )


class MedicationRequest(BaseModel):
    action: MedicationAction
    profile_id: str = Field(default="9000001", max_length=100)
    data: dict[str, Any] = Field(default_factory=dict)


class MedicationResponse(BaseModel):
    action: MedicationAction
    message: str
    medications: list[dict[str, Any]] = Field(default_factory=list)


class CareBriefResponse(BaseModel):
    profile_id: str
    brief: str


class GreetingResponse(BaseModel):
    greeting: str
    follow_up_event_id: str | None = None


class InsightCard(BaseModel):
    type: Literal[
        "medication_reminder",
        "trend_positive",
        "followup_question",
        "report_alert",
    ]
    icon_emoji: str
    text: str


class ReportResponse(BaseModel):
    profile_id: str
    filename: str
    interpretation: str


class MemorySearchRequest(BaseModel):
    profile_id: str = Field(default="9000001", max_length=100)
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=5, ge=1, le=20)


class MemorySearchResponse(BaseModel):
    available: bool
    results: list[str]


class IntentClassificationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class IntentClassificationResponse(BaseModel):
    intents: list[IntentName]


class IntentExtractionResponse(BaseModel):
    primary_intent: str
    intents: list[IntentName]
    normalized_query: str
    detected_language: Literal["en", "hi", "hinglish"]
    confidence: float
    needs_clarification: bool


class TextToSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5_000)
    lang: Literal["en", "hi"] = "en"


class AuthProfileRequest(BaseModel):
    name: str = Field(default="", max_length=120)


class AuthSignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=200)


class FamilyMemberCreate(BaseModel):
    owner_id: str
    name: str
    relation: str
    age: int = Field(ge=0, le=130)
    blood_group: str
    known_conditions: list[str] = Field(default_factory=list)


class MedicationCreate(BaseModel):
    user_id: str
    drug_name: str
    dose: str
    frequency: str
    timing: list[str] = Field(default_factory=list)
    with_food: bool = False
    family_member_id: str | None = None


class HistoryResponse(BaseModel):
    user_id: str
    family_member_id: str | None = None
    history: str


class InteractionCheckRequest(BaseModel):
    user_id: str
    new_drug: str
    family_member_id: str | None = None


class InteractionCheckResponse(BaseModel):
    message: str
