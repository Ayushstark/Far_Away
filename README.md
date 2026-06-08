# CareOS Healthcare Agent

An early-stage healthcare assistant that coordinates specialist AI agents for
symptom triage, report explanation, medication support, care planning, family
visibility, and emergency escalation.

![CareOS Healthcare Architecture](docs/careos_healthcare_architecture.svg)

## Current Stage

**Phase 0 complete:** the project has been scaffolded into a working full-stack
prototype with a Next.js dashboard, FastAPI backend, five healthcare agent
modules, a master orchestrator, ChromaDB memory hooks, Supabase-ready
configuration, and local developer setup.

**Status:** hackathon MVP foundation. The app can route a user message to
specialist agents, detect emergency language, return safe informational output,
and run locally with placeholder credentials. Claude-powered personalized
responses activate after adding a valid Anthropic API key.

## What CareOS Does

- Accepts user health input through the web dashboard.
- Uses a master orchestrator to infer intent and select relevant agents.
- Routes work across five specialist agents:
  - Symptom analyst
  - Medical report reader
  - Medication manager
  - Care coordinator
  - Emergency detector
- Stores and retrieves patient context through a ChromaDB-backed memory layer.
- Keeps the data model ready for family dashboards and Supabase persistence.
- Produces plain-language insights, doctor-visit briefs, proactive nudges, and
  emergency escalation guidance.

## Tech Stack

| Layer | Tools |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| UI + Client | Axios, Lucide React |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| AI | Anthropic Claude API |
| Memory | ChromaDB persistent vector store |
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

## Environment Variables

```env
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-sonnet-4-20250514
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
CHROMA_PATH=memory/chroma
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The committed `.env.example` shows the expected variables. The real `.env` file
is intentionally ignored by Git.

## Implemented So Far

- Full project scaffold matching the requested architecture.
- Next.js dashboard with specialist agent navigation and chat input.
- FastAPI API with `/health` and `/api/chat` endpoints.
- Master orchestrator service.
- Five specialist agent definitions.
- Anthropic Claude service wrapper with no-key fallback.
- Emergency red-flag detection.
- ChromaDB memory adapter with graceful fallback if local embedding storage is
  unavailable.
- Project README, env template, dependency files, and Git ignore rules.

## Roadmap

- Add real PDF upload and report parsing workflow.
- Replace keyword routing with LLM-based intent planning.
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
