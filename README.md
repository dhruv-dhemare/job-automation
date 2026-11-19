# Personal AI Internship Outreach Automation

This is a deliberately small, personal tool. The first slice discovers real companies through Tavily and stores deduplicated results in a local SQLite database. It does not send email and it does not invent contact details.

## Minimum viable architecture

1. Search provider: Tavily returns web results for internship and software-engineering queries.
2. Local tracker: SQLite keeps a durable, single-user record without a database server.
3. Later integrations: Claude writes drafts; Gmail creates drafts and sends only after approval; Google Sheets can become an export/view once the workflow is stable.
4. Interface: start with the CLI. Add Streamlit only after discovery and draft review work end-to-end.

The resume is intentionally read from `RESUME_PATH`; no resume file was present in the supplied workspace, so the application currently makes no claims about qualifications beyond data you later provide.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Add SEARCH_API_KEY to .env
python main.py --count 10
```

If the key is missing, the command prints a short setup message and exits without changing the tracker.

Tavily has a free tier that is suitable for development, but check its current pricing before regular use. The code keeps the provider behind one function so a different search API can be added without changing tracking or future email code.

## Safety boundaries

- Search results are source URLs, not verified facts; compensation must be researched and recorded separately.
- No email addresses are generated. Contact discovery and verification will be a separate phase.
- Gmail sending will remain approval-gated; the initial implementation has no Gmail permissions.
- API keys belong only in `.env`, which should not be committed.
