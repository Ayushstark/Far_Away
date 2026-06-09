from io import BytesIO

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.care_coordinator import brief_to_pdf, create_care_brief
from agents.report_reader import read_report
from backend.app.schemas import (
    CareBriefResponse,
    ChatRequest,
    ChatResponse,
    MedicationRequest,
    MedicationResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    ReportResponse,
    IntentClassificationRequest,
    IntentClassificationResponse,
)
from backend.app.services.intent_classifier import classify_intent
from backend.app.services.orchestrator import Orchestrator
from backend.app.config import settings

app = FastAPI(title="CareOS Healthcare API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
orchestrator = Orchestrator()


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "semantic_memory": orchestrator.memory.available,
        "gemini_configured": bool(settings.gemini_api_key),
        "groq_configured": bool(settings.groq_api_key),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await orchestrator.run(request.message, request.profile_id)


@app.post("/api/intents/classify", response_model=IntentClassificationResponse)
async def classify(request: IntentClassificationRequest) -> IntentClassificationResponse:
    return IntentClassificationResponse(intents=await classify_intent(request.message))


@app.post("/api/memory/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest) -> MemorySearchResponse:
    return MemorySearchResponse(
        available=orchestrator.memory.available,
        results=orchestrator.memory.recall(request.profile_id, request.query, request.limit),
    )


@app.post("/api/reports/read", response_model=ReportResponse)
async def report_reader(
    profile_id: str = "demo-user",
    file: UploadFile = File(...),
) -> ReportResponse:
    filename = file.filename or "report.pdf"
    if file.content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF reports are supported.")
    interpretation = await read_report(await file.read(), profile_id, orchestrator.memory)
    return ReportResponse(
        profile_id=profile_id,
        filename=filename,
        interpretation=interpretation,
    )


@app.post("/api/medications", response_model=MedicationResponse)
async def medications(request: MedicationRequest) -> MedicationResponse:
    try:
        message = await orchestrator.medication_manager.run(
            request.action,
            request.data,
            request.profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MedicationResponse(
        action=request.action,
        message=message,
        medications=orchestrator.medications.list(request.profile_id),
    )


@app.get("/api/care-brief/{profile_id}", response_model=CareBriefResponse)
async def care_brief(profile_id: str) -> CareBriefResponse:
    brief = await create_care_brief(profile_id, orchestrator.memory, orchestrator.medications)
    return CareBriefResponse(profile_id=profile_id, brief=brief)


@app.get("/api/care-brief/{profile_id}/pdf")
async def care_brief_pdf(profile_id: str) -> StreamingResponse:
    brief = await create_care_brief(profile_id, orchestrator.memory, orchestrator.medications)
    return StreamingResponse(
        BytesIO(brief_to_pdf(brief)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="careos-{profile_id}-brief.pdf"'},
    )
