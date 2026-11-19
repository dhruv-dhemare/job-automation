# Personal AI Internship Outreach Automation

This is a deliberately small, personal tool. It discovers real companies through Tavily, finds optional recruiting contacts through Hunter, uses Claude to write drafts from your resume, and creates Gmail drafts for your approval. It never sends email automatically and never invents contact details.

## Minimum viable architecture

1. Search provider: Tavily returns web results for internship and software-engineering queries.
2. Local tracker: SQLite keeps a durable, single-user record without a database server.
3. AI writer: Gemini is the default low-cost provider, and Ollama is available for fully local writing when cloud APIs are unavailable. The writer reads the resume plus supplied company/contact data, then returns two grounded email variants. Claude remains optional.
4. Gmail: OAuth creates drafts with the resume attached. Sending is a separate explicit action in Gmail.
5. Interface: `app.py` is a small Streamlit dashboard; the CLI remains available for discovery.

The resume is intentionally read from `RESUME_PATH`; no resume file was present in the supplied workspace, so the application currently makes no claims about qualifications beyond data you later provide.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Add SEARCH_API_KEY to .env
python main.py --count 10
# or
streamlit run app.py
```

If the key is missing, the command prints a short setup message and exits without changing the tracker.

Add your resume at `data/resume.pdf`, add `GEMINI_API_KEY`, and optionally add `HUNTER_API_KEY`. Gemini API keys can be created in [Google AI Studio](https://aistudio.google.com/app/apikey); its free tier is subject to current rate limits. The app checks which Gemini models your key can call and selects an available one automatically. To use Claude instead, set `AI_PROVIDER=claude` and add `ANTHROPIC_API_KEY`. For Gmail, create a Google Cloud OAuth desktop credential JSON, save it as `credentials.json`, and complete the browser login the first time you create a draft.

If Gemini is unavailable, install [Ollama for Windows](https://ollama.com/download/windows), run `ollama pull llama3.2:3b`, and set `AI_PROVIDER=ollama`. This keeps resume and contact data on your computer during email generation.

## Safety boundaries

- Search results are source URLs, not verified facts; compensation must be researched and recorded separately.
- Email addresses come only from Hunter and are shown with their verification status.
- Gmail draft creation uses OAuth; sending is never automatic.
- API keys belong only in `.env`, which should not be committed.
