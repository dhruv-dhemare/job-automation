"""Claude-powered resume matching and email drafting."""

import json
from pathlib import Path
from typing import Any

from config import settings


def _prompt(company: dict[str, Any], contact: dict[str, Any], resume: str) -> str:
    return f"""You write truthful internship outreach emails.

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


def load_resume(path: Path | None = None) -> str:
    path = path or settings.resume_path
    if not path.exists():
        raise FileNotFoundError(f"Resume not found at {path}. Add your PDF or set RESUME_PATH in .env.")
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
    return path.read_text(encoding="utf-8").strip()


def generate_emails(company: dict[str, Any], contact: dict[str, Any], resume: str | None = None) -> dict[str, str]:
    resume = resume or load_resume()
    if settings.ai_provider.lower() == "gemini":
        return _generate_with_gemini(company, contact, resume)
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing from .env")
    from anthropic import Anthropic

    prompt = _prompt(company, contact, resume)
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


def _generate_with_gemini(company: dict[str, Any], contact: dict[str, Any], resume: str) -> dict[str, str]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")
    import requests

    model = _available_gemini_model(requests)
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": settings.gemini_api_key},
        json={
            "contents": [{"parts": [{"text": _prompt(company, contact, resume)}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini request failed ({response.status_code}): {response.text[:500]}")
    candidates = response.json().get("candidates", [])
    text = candidates[0]["content"]["parts"][0]["text"] if candidates else ""
    try:
        result = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini returned invalid JSON; try again.") from error
    required = {"professional_subject", "professional_body", "technical_subject", "technical_body"}
    if not required.issubset(result):
        raise RuntimeError("Gemini response was missing required email fields.")
    return {key: str(result[key]).strip() for key in required}


def _available_gemini_model(requests_module: Any) -> str:
    """Choose a model the current key can actually call."""
    response = requests_module.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": settings.gemini_api_key},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Could not list Gemini models ({response.status_code}): {response.text[:500]}")
    available = {
        item["name"].removeprefix("models/")
        for item in response.json().get("models", [])
        if "generateContent" in item.get("supportedGenerationMethods", [])
    }
    preferences = [settings.gemini_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in preferences:
        if model in available:
            return model
    if available:
        return sorted(available)[0]
    raise RuntimeError("This Gemini API key has no model that supports generateContent.")
