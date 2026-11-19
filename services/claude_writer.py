"""Claude-powered resume matching and email drafting."""

import json
from pathlib import Path
from typing import Any

from config import settings


def load_resume(path: Path | None = None) -> str:
    path = path or settings.resume_path
    if not path.exists():
        raise FileNotFoundError(f"Resume not found at {path}. Add your PDF or set RESUME_PATH in .env.")
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
    return path.read_text(encoding="utf-8").strip()


def generate_emails(company: dict[str, Any], contact: dict[str, Any], resume: str | None = None) -> dict[str, str]:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing from .env")
    resume = resume or load_resume()
    from anthropic import Anthropic

    prompt = f"""You write truthful internship outreach emails.

Candidate resume:
{resume}

Company information:
{json.dumps(company, ensure_ascii=False)}

Recipient:
{json.dumps(contact, ensure_ascii=False)}

Return JSON only with these keys: professional_subject, professional_body,
technical_subject, technical_body. Each body must be 120-180 words. Use only
facts in the resume and supplied company information. Do not invent an opening,
technology, relationship, compensation, or achievement. Ask whether there may
be a 2027 software engineering internship or a suitable referral. Use a natural
professional tone and a concise call to action. Sign as Dhruv Dhemare.
"""
    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=1200,
        temperature=0.3,
        system="You are a careful recruiting-writing assistant. Output valid JSON only.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Claude returned invalid JSON; try again.") from error
    required = {"professional_subject", "professional_body", "technical_subject", "technical_body"}
    if not required.issubset(result):
        raise RuntimeError("Claude response was missing required email fields.")
    return {key: str(result[key]).strip() for key in required}
