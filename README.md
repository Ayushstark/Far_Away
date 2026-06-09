# CareOS Healthcare Agent

An early-stage healthcare assistant that coordinates specialist AI agents for
symptom triage, report explanation, medication support, care planning, family
visibility, and emergency escalation.

![CareOS Healthcare Architecture](docs/careos_healthcare_architecture.svg)

## Current Stage

**Phase 1 in progress:** the project is now a working full-stack prototype with
a Next.js dashboard, FastAPI backend, structured intent classifier, five
healthcare agents, emergency-first orchestration, semantic ChromaDB memory,
Supabase-ready medication storage, PDF report reading, and doctor briefs.

**Status:** hackathon MVP foundation. The app can route a user message to
specialist agents, detect emergency language, return safe informational output,
and run locally with placeholder credentials. Gemini and Groq-powered responses
activate after adding their API keys.

## What CareOS Does

- Accepts user health input through the web dashboard.
- Uses a structured intent classifier and master orchestrator to select agents.
- Routes work across five specialist agents:
  - Symptom analyst
  - Medical report reader
  - Medication manager
  - Care coordinator
  - Emergency detector
- Stores and semantically retrieves patient context through ChromaDB.
- Keeps the data model ready for family dashboards and Supabase persistence.
- Produces plain-language insights, doctor-visit briefs, proactive nudges, and
  emergency escalation guidance.

## Tech Stack

| Layer | Tools |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| UI + Client | Axios, Lucide React |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| AI brain + PDF vision | Google Gemini 2.5 Flash |
| Fast inference + fallback | Groq Llama 3.1 8B Instant |
| Memory | ChromaDB with Gemini Embeddings and offline fallback |
| Data Layer | Supabase-ready config |
| Documents | PyPDF2, python-multipart |
| Deployment Target | Vercel for frontend, Railway or similar for backend |

## Architecture

```text
User input
  -> Master orchestrator
    -> Symptom analyst
    -> Report reader
    -> Medication manager
    -> Care coordinator
    -> Emergency detector
  -> Health memory layer
  -> Family dashboard layer
  -> User-facing outputs
```

The backend keeps agent routing separate from each agent's prompt and purpose,
so the system can grow from keyword routing into richer model-based planning
without changing the public API.

## Project Structure

```text
agents/      Specialist healthcare agent definitions
backend/     FastAPI app, schemas, services, and requirements
docs/        Architecture reference assets
frontend/    Next.js dashboard
memory/      ChromaDB storage adapter and memory notes
```

## Local Setup

1. Install Node.js and Python 3.11+.
2. Replace placeholder values in `.env` with real credentials.
3. Install and run the backend:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.app.main:app --reload
```

4. Install and run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

5. Open the app:

```text
Frontend: http://localhost:3000
API docs: http://localhost:8000/docs
Health check: http://localhost:8000/health
```

## API Surface

| Endpoint | Purpose |
| --- | --- |
| `POST /api/chat` | Emergency-first multi-agent orchestration |
| `POST /api/intents/classify` | Structured multi-intent classification |
| `POST /api/memory/search` | User-scoped semantic health-memory search |
| `POST /api/reports/read` | PDF extraction, interpretation, and memory storage |
| `POST /api/medications` | Add, list, explain, or check medication interactions |
| `GET /api/care-brief/{profile_id}` | Generate a printer-friendly care brief |
| `GET /api/care-brief/{profile_id}/pdf` | Download the care brief as a PDF |

## Environment Variables

```env
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
CHROMA_PATH=memory/chroma
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The committed `.env.example` shows the expected variables. The real `.env` file
is intentionally ignored by Git.

### Provider Routing

| Workload | Primary | Automatic fallback |
| --- | --- | --- |
| Intent classification, emergency reasoning, response merging | Gemini 2.5 Flash | Groq |
| PDF report understanding | Gemini 2.5 Flash multimodal | Extracted-text fallback |
| Fast specialist responses | Groq Llama 3.1 8B Instant | Gemini |
| Semantic memory embeddings | Gemini Embeddings | Offline deterministic embeddings |

When Supabase is configured, CareOS expects `medications` and
`emergency_alerts` tables. Local development continues with safe fallbacks if
Supabase or those tables are unavailable.

## Implemented So Far

- Full project scaffold matching the requested architecture.
- Next.js dashboard with specialist agent navigation and chat input.
- FastAPI APIs for chat, memory search, report reading, medications, and briefs.
- Emergency-first master orchestrator and structured intent classifier.
- Five dedicated specialist agent implementations.
- Gemini-first reasoning and Groq-first fast-inference provider router.
- Automatic Gemini/Groq provider fallback when one API is unavailable.
- Emergency red-flag detection with structured severity and immediate steps.
- ChromaDB semantic search using deterministic offline embeddings.
- PDF report extraction and report-memory storage.
- Supabase medication repository with a local development fallback.
- Printer-friendly care brief and downloadable PDF generation.
- Project README, env template, dependency files, and Git ignore rules.

## Roadmap

- Add richer structured extraction for PDF lab tables.
- Expand classifier evaluation and multi-intent routing tests.
- Add Supabase schema for profiles, family members, medications, and alerts.
- Generate downloadable doctor briefs.
- Add medication reminder and proactive nudge scheduling.
- Build family dashboard views for dependent profiles.
- Add authentication and role-based access.
- Add automated tests for orchestration, emergency detection, and memory.
- Prepare Vercel and Railway deployment configs.

## Safety Notice

CareOS is an informational assistant and prototype, not a medical device. It
must not diagnose, prescribe, or delay emergency care. For urgent symptoms,
users should contact local emergency services immediately. Production use would
require clinical review, privacy review, security hardening, and regulatory
assessment.
