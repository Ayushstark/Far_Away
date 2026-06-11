"""Keep automated tests isolated from real API keys and live Supabase data."""

import os

os.environ["GEMINI_API_KEY"] = "your_test_key"
os.environ["GROQ_API_KEY"] = "your_test_key"
os.environ["SUPABASE_URL"] = "your_test_url"
os.environ["SUPABASE_KEY"] = "your_test_key"
os.environ["CHROMA_PATH"] = "Chroma_data/test"
