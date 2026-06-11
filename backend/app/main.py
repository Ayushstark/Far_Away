from io import BytesIO

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.care_coordinator import brief_to_pdf, create_care_brief
from agents.report_reader import read_report
from backend.app import db
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
    FamilyMemberCreate,
    MedicationCreate,
    HistoryResponse,
    InteractionCheckRequest,
    InteractionCheckResponse,
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


@app.post("/chat", response_model=ChatResponse)
@app.post("/api/chat", response_model=ChatResponse, include_in_schema=False)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        history = db.get_health_history(request.profile_id, request.family_member_id)
        medications = db.get_medications(request.profile_id, request.family_member_id)
        response = await orchestrator.run(
            request.message,
            request.profile_id,
            health_history=history,
            current_medications=medications,
        )
        db.save_health_event(
            user_id=request.profile_id,
            family_member_id=request.family_member_id,
            event_type=response.intents[0] if response.intents else "chat",
            description=request.message,
            ai_response=response.message,
            severity=(
                response.emergency_details.severity
                if response.emergency_details
                else "none"
            ),
            body_part=None,
        )
        return response
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Database operation failed: {exc}") from exc


@app.post("/api/intents/classify", response_model=IntentClassificationResponse)
async def classify(request: IntentClassificationRequest) -> IntentClassificationResponse:
    return IntentClassificationResponse(intents=await classify_intent(request.message))


@app.post("/api/memory/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest) -> MemorySearchResponse:
    return MemorySearchResponse(
        available=orchestrator.memory.available,
        results=orchestrator.memory.recall(request.profile_id, request.query, request.limit),
    )


@app.post("/upload-report", response_model=ReportResponse)
@app.post("/api/reports/read", response_model=ReportResponse, include_in_schema=False)
async def report_reader(
    file: UploadFile = File(...),
    profile_id: str = Form(default="demo-user"),
    family_member_id: str | None = Form(default=None),
    report_type: str = Form(default="blood report"),
) -> ReportResponse:
    filename = file.filename or "report.pdf"
    if file.content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF reports are supported.")
    content = await file.read()
    try:
        file_url = db.upload_report_file(profile_id, filename, content)
        past_reports = db.get_past_reports_summary(profile_id, family_member_id)
        interpretation = await read_report(
            content,
            profile_id,
            orchestrator.memory,
            past_reports_summary=past_reports,
        )
        db.save_report(
            user_id=profile_id,
            family_member_id=family_member_id,
            report_type=report_type,
            file_url=file_url,
            ai_summary=interpretation,
            flagged_values={},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Report storage failed: {exc}") from exc
    return ReportResponse(
        profile_id=profile_id,
        filename=filename,
        interpretation=interpretation,
    )


@app.post("/family/add")
async def add_family_member(request: FamilyMemberCreate) -> dict:
    try:
        return db.create_family_member(**request.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not add family member: {exc}") from exc


@app.get("/family/{owner_id}")
async def family_members(owner_id: str) -> list[dict]:
    try:
        return db.get_family_members(owner_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load family members: {exc}") from exc


@app.get("/profile/{user_id}")
async def user_profile(user_id: str) -> dict:
    try:
        profile = db.get_user(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User not found.")
        return profile
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load profile: {exc}") from exc


@app.post("/medications/add")
async def add_medication(request: MedicationCreate) -> dict:
    try:
        return db.add_medication(**request.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not add medication: {exc}") from exc


@app.get("/medications/{user_id}")
async def list_medications(
    user_id: str,
    family_member_id: str | None = None,
) -> list[dict]:
    try:
        return db.get_medications(user_id, family_member_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load medications: {exc}") from exc


@app.post("/medications/check-interactions", response_model=InteractionCheckResponse)
async def check_medication_interactions(
    request: InteractionCheckRequest,
) -> InteractionCheckResponse:
    try:
        message = await orchestrator.medication_manager.run(
            "check_interactions",
            {
                "new_drug": request.new_drug,
                "current_medications": db.get_medications(
                    request.user_id,
                    request.family_member_id,
                ),
            },
            request.user_id,
        )
        return InteractionCheckResponse(message=message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Interaction check failed: {exc}") from exc


@app.get("/reports/{user_id}")
async def reports(
    user_id: str,
    family_member_id: str | None = None,
) -> list[dict]:
    try:
        return db.get_reports(user_id, family_member_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load reports: {exc}") from exc


@app.get("/history/{user_id}", response_model=HistoryResponse)
async def health_history(
    user_id: str,
    family_member_id: str | None = None,
) -> HistoryResponse:
    try:
        return HistoryResponse(
            user_id=user_id,
            family_member_id=family_member_id,
            history=db.get_health_history(user_id, family_member_id, limit=100),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load history: {exc}") from exc


@app.get("/doctor-brief/{user_id}", response_model=CareBriefResponse)
async def doctor_brief(
    user_id: str,
    family_member_id: str | None = None,
) -> CareBriefResponse:
    try:
        brief = await create_care_brief(
            user_id,
            health_history=db.get_health_history(user_id, family_member_id, limit=100),
            current_medications=db.get_medications(user_id, family_member_id),
            user_profile=db.get_user(user_id),
        )
        return CareBriefResponse(profile_id=user_id, brief=brief)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not generate brief: {exc}") from exc


@app.post("/api/medications", response_model=MedicationResponse)
async def medications(request: MedicationRequest) -> MedicationResponse:
    try:
        current = db.get_medications(request.profile_id)
        if request.action == "add":
            medication = db.add_medication(
                user_id=request.profile_id,
                drug_name=str(request.data.get("name") or request.data.get("drug_name") or ""),
                dose=str(request.data.get("dose") or ""),
                frequency=str(request.data.get("frequency") or ""),
                timing=request.data.get("timing") or request.data.get("times") or [],
                with_food=bool(request.data.get("with_food", False)),
            )
            message = f"Saved {medication['drug_name']} {medication['dose']}."
        elif request.action == "list":
            message = "Loaded active medications."
        else:
            message = await orchestrator.medication_manager.run(
                request.action,
                {**request.data, "current_medications": current},
                request.profile_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Medication operation failed: {exc}") from exc
    return MedicationResponse(
        action=request.action,
        message=message,
        medications=db.get_medications(request.profile_id),
    )


@app.get("/api/care-brief/{profile_id}", response_model=CareBriefResponse)
async def care_brief(profile_id: str) -> CareBriefResponse:
    return await doctor_brief(profile_id)


@app.get("/api/care-brief/{profile_id}/pdf")
async def care_brief_pdf(
    profile_id: str,
    family_member_id: str | None = None,
) -> StreamingResponse:
    brief = await create_care_brief(
        profile_id,
        health_history=db.get_health_history(profile_id, family_member_id, limit=100),
        current_medications=db.get_medications(profile_id, family_member_id),
        user_profile=db.get_user(profile_id),
    )
    return StreamingResponse(
        BytesIO(brief_to_pdf(brief)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="careos-{profile_id}-brief.pdf"'},
    )
