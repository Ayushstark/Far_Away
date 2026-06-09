# Health memory

ChromaDB persists user-scoped semantic health memories in `memory/chroma/`.
CareOS uses `gemini-embedding-001` when `GEMINI_API_KEY` is configured, with a
deterministic offline embedding fallback for local development and tests.

Supabase holds structured data such as medications when credentials and the
required tables are configured. The medication repository falls back to local
in-memory storage during development.
