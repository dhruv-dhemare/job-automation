"""Discover and rank internship-relevant companies using a search provider."""

from dataclasses import asdict, dataclass
import re
from typing import Any

import requests

from config import settings


TARGET_ROLES = (
    "software engineering intern",
    "backend developer intern",
    "full stack developer intern",
    "frontend developer intern",
    "python developer intern",
    "ai ml intern",
    "java developer intern",
)

TARGET_LOCATIONS = ("Bangalore software product companies", "Pune fintech SaaS companies", "India remote-first software startups")
EXCLUDED_DOMAINS = {
    "indeed.com", "linkedin.com", "glassdoor.com", "handshake.com", "wayup.com",
    "ziprecruiter.com", "simplify.jobs", "remotive.com", "wantjob.in", "hiredoor.in",
    "wellfound.com", "internshala.com", "naukri.com", "cutshort.io", "instahyre.com",
    "remoteok.com", "weworkremotely.com", "jooble.org", "talent.com", "monster.com",
    "foundit.in", "foundit.com", "builtin.com", "timesjobs.com", "shine.com",
    "careerbuilder.com", "adzuna.com", "jobstreet.com", "dice.com", "remote.co",
    "himalayas.app", "startup.jobs", "freshersworld.com", "apna.co", "careerjet.com",
}


@dataclass
class Company:
    name: str
    website: str
    careers_url: str
    description: str
    relevant_opening: str
    source_url: str
    match_score: int
    match_reason: str
    compensation: str = "Unknown"
    compensation_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _domain(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()


def _score(text: str) -> tuple[int, str]:
    lowered = text.lower()
    points = 0
    reasons: list[str] = []
    for keyword, value, reason in (
        ("intern", 25, "has an internship signal"),
        ("software engineer", 15, "mentions software engineering"),
        ("backend", 10, "matches backend work"),
        ("python", 8, "matches Python"),
        ("java", 8, "matches Java"),
        ("ai", 8, "matches AI/ML"),
        ("fintech", 5, "matches fintech"),
        ("saas", 5, "matches SaaS"),
        ("remote", 4, "supports remote work"),
    ):
        if keyword in lowered:
            points += value
            reasons.append(reason)
    return min(points, 100), ", ".join(reasons) or "matches the search query"


def _query(location: str) -> str:
    return (
        f"{location} company websites engineering teams founders CTOs "
        "product fintech SaaS AI startup technology company "
        "-job-board -aggregator -job-posting -course -training"
    )


def discover_companies(count: int = 10) -> list[Company]:
    """Return real search results. Raises a useful error if the provider is not configured."""
    if not settings.search_api_key:
        raise RuntimeError(
            "SEARCH_API_KEY is not configured. Add a Tavily API key to .env, "
            "then run the command again."
        )
    if settings.search_provider.lower() != "tavily":
        raise RuntimeError(f"Unsupported SEARCH_PROVIDER: {settings.search_provider}")

    raw_results = []
    for location in TARGET_LOCATIONS:
        response = requests.post(
            settings.search_api_url,
            headers={"Content-Type": "application/json"},
            json={
                "api_key": settings.search_api_key,
                "query": _query(location),
                "search_depth": "advanced",
                "max_results": max(count, 5),
                "include_answer": False,
                "exclude_domains": sorted(EXCLUDED_DOMAINS),
            },
            timeout=30,
        )
        response.raise_for_status()
        raw_results.extend(response.json().get("results", []))

    companies: list[Company] = []
    seen_domains: set[str] = set()
    for result in raw_results:
        url = result.get("url", "")
        domain = _domain(url)
        if not domain or any(domain == blocked or domain.endswith("." + blocked) for blocked in EXCLUDED_DOMAINS):
            continue
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        title = result.get("title", "").strip()
        content = result.get("content", "").strip()
        generic_titles = {"careers", "jobs", "company", "about us", "software engineer jobs"}
        if title.lower() in generic_titles:
            title = domain.split(".")[0].replace("-", " ").replace("_", " ").title()
        score, reason = _score(f"{title} {content}")
        if not any(word in f"{url} {title} {content}".lower() for word in ("company", "software", "technology", "engineering", "fintech", "saas", "startup")):
            continue
        companies.append(
            Company(
                name=title or domain,
                website=f"https://{domain}",
                careers_url=url,
                description=content[:500],
                relevant_opening=title,
                source_url=url,
                match_score=score,
                match_reason=reason,
            )
        )

    return sorted(companies, key=lambda item: item.match_score, reverse=True)[:count]
