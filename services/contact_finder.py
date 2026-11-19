"""Optional Hunter domain search. Returned emails are never guessed locally."""

import requests

from config import settings


def find_contacts(website: str) -> list[dict[str, str]]:
    if not settings.hunter_api_key:
        raise RuntimeError("HUNTER_API_KEY is missing from .env")
    domain = website.split("//", 1)[-1].split("/", 1)[0]
    response = requests.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": settings.hunter_api_key, "limit": 10},
        timeout=30,
    )
    response.raise_for_status()
    contacts = []
    for item in response.json().get("data", {}).get("emails", []):
        department = (item.get("department") or "").lower()
        position = (item.get("position") or "").lower()
        if any(word in f"{department} {position}" for word in ("hr", "human", "recruit", "talent", "founder", "cto")):
            contacts.append(
                {
                    "name": " ".join(filter(None, [item.get("first_name"), item.get("last_name")])),
                    "designation": item.get("position") or item.get("department") or "Recruiting contact",
                    "email": item.get("value", ""),
                    "verification_status": item.get("verification", {}).get("status", "unknown"),
                    "linkedin_url": item.get("linkedin", ""),
                    "source": "Hunter domain search",
                }
            )
    return contacts[:3]
