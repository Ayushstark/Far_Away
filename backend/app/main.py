from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.schemas import ChatRequest, ChatResponse
from backend.app.services.orchestrator import Orchestrator

app = FastAPI(title="CareOS Healthcare API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
orchestrator = Orchestrator()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await orchestrator.run(request.message, request.profile_id)
