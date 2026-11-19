"""Claude-powered resume matching and email drafting."""

import json
import re
import time
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
    resume = (resume or load_resume())[:12000]
    if settings.ai_provider.lower() == "ollama":
        return _generate_with_ollama(company, contact, resume)
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

    model = settings.gemini_model
    payload = {
        "contents": [{"parts": [{"text": _prompt(company, contact, resume)}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
    }
    response = _post_with_retry(requests, model, payload)
    if response.status_code == 404:
        model = _available_gemini_model(requests)
        response = _post_with_retry(requests, model, payload)
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
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"Could not list Gemini models ({response.status_code}): {response.text[:500]}")
    available = {
        item["name"].removeprefix("models/")
        for item in response.json().get("models", [])
        if "generateContent" in item.get("supportedGenerationMethods", [])
    }
    preferences = [settings.gemini_model, "gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in preferences:
        if model in available:
            return model
    if available:
        return sorted(available)[0]
    raise RuntimeError("This Gemini API key has no model that supports generateContent.")


def _generate_with_ollama(company: dict[str, Any], contact: dict[str, Any], resume: str) -> dict[str, str]:
    import requests

    professional = _ollama_text_request(
        requests,
        f"""Write one concise professional internship outreach email as plain text.
Candidate resume: {resume}
Company: {json.dumps(company, ensure_ascii=False)}
Recipient: {json.dumps(contact, ensure_ascii=False)}
Use only supplied facts. Mention one relevant candidate achievement, ask about a 2027 software engineering internship, and sign as Dhruv Dhemare. Include greeting and closing. Do not output JSON, labels, analysis, or a subject line.""",
    )
    technical = _ollama_text_request(
        requests,
        f"""Write one technical but natural internship outreach email as plain text.
Candidate resume: {resume}
Company: {json.dumps(company, ensure_ascii=False)}
Recipient: {json.dumps(contact, ensure_ascii=False)}
Use only supplied facts. Mention relevant technologies and one concrete achievement, ask about a 2027 software engineering internship, and sign as Dhruv Dhemare. Include greeting and closing. Do not output JSON, labels, analysis, or a subject line.""",
    )
    company_name = company.get("name", "the company")
    return {
        "professional_subject": f"Software Engineering Internship Inquiry - {company_name}",
        "professional_body": professional,
        "technical_subject": f"Technical Internship Inquiry - {company_name}",
        "technical_body": technical,
    }


def _ollama_text_request(requests_module: Any, prompt: str) -> str:
    try:
        session = requests_module.Session()
        session.trust_env = False
        response = session.post(
            settings.ollama_url,
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "options": {"temperature": 0.3, "num_predict": 320, "num_ctx": 4096}},
            timeout=180,
        )
    except requests_module.exceptions.RequestException as error:
        raise RuntimeError(f"Could not connect to Ollama at {settings.ollama_url}: {error}") from error
    if not response.ok:
        raise RuntimeError(f"Ollama request failed ({response.status_code}): {response.text[:300]}")
    text = response.json().get("response", "").strip()
    if not text:
        raise RuntimeError("Ollama returned an empty email.")
    return text


def _parse_json_or_text(raw: str) -> dict[str, Any]:
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                result = json.loads(cleaned[start : end + 1])
                return result if isinstance(result, dict) else {}
            except json.JSONDecodeError:
                pass
    # Small local models sometimes truncate JSON or repeat keys. Recover only
    # the first four requested fields; never pass raw JSON into an email body.
    result: dict[str, Any] = {}
    for key in ("professional_subject", "professional_body", "technical_subject", "technical_body"):
        matches = re.findall(rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)"', cleaned, flags=re.DOTALL)
        if matches:
            try:
                result[key] = json.loads('"' + matches[0] + '"')
            except json.JSONDecodeError:
                result[key] = matches[0].replace("\\n", "\n").replace('\\"', '"')
    return result


def _post_with_retry(requests_module: Any, model: str, payload: dict[str, Any]) -> Any:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(3):
        try:
            response = requests_module.post(
                url,
                params={"key": settings.gemini_api_key},
                json=payload,
                timeout=60,
            )
        except requests_module.exceptions.ReadTimeout:
            if attempt == 2:
                raise RuntimeError("Gemini timed out three times. Try again later or use another network.")
            time.sleep(5 * (attempt + 1))
            continue
        if response.status_code not in {429, 500, 503, 504} or attempt == 2:
            return response
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Gemini did not respond after retries.")
