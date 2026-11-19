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
    "github.com", "webneco.com", "yourstory.com", "inc42.com", "tracxn.com",
    "ambitionbox.com", "startup-talky.com", "analyticsinsight.net",
}

LISTING_PHRASES = (
    "top ", "list of", "companies in", "startups in", "you should know",
    "curated list", "directory", "salary", "services areas", "position closed",
    "jobs, salaries", "hiring guide", "companies based in",
)
DISCOVERY_ONLY_DOMAINS = {
    "linkedin.com", "wellfound.com", "builtin.com", "github.com", "yourstory.com",
    "inc42.com", "tracxn.com", "startup-talky.com", "analyticsinsight.net",
}


def _is_direct_company_result(url: str, title: str, content: str) -> bool:
    lowered_url = url.lower()
    lowered_text = f"{title} {content}".lower()
    if any(phrase in lowered_text for phrase in LISTING_PHRASES):
        return False
    if any(part in lowered_url for part in ("/blog/", "/article/", "/posts/", "/list/", "/tag/", "/wiki/")):
        return False
    return any(part in lowered_url for part in ("/about", "/company", "/career", "/jobs", "/join", "/contact")) or lowered_url.count("/") <= 3


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


def _lead_queries() -> tuple[str, ...]:
    return (
        "site:linkedin.com/company software startup Bangalore OR Bengaluru",
        "site:linkedin.com/company fintech SaaS startup Pune",
        "site:wellfound.com/company software startup India remote",
    )


def _candidate_name(title: str) -> str:
    cleaned = re.split(r"\s+(?:\||-|–)\s+", title, maxsplit=1)[0].strip()
    if not cleaned or any(phrase in cleaned.lower() for phrase in LISTING_PHRASES):
        return ""
    return cleaned


def _resolve_official_website(name: str) -> tuple[str, str, str] | None:
    response = requests.post(
        settings.search_api_url,
        headers={"Content-Type": "application/json"},
        json={
            "api_key": settings.search_api_key,
            "query": f'"{name}" official company website',
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": False,
            "exclude_domains": sorted(EXCLUDED_DOMAINS),
        },
        timeout=30,
    )
    response.raise_for_status()
    for result in response.json().get("results", []):
        url = result.get("url", "")
        domain = _domain(url)
        title = result.get("title", "").strip()
        content = result.get("content", "").strip()
        if domain and not any(domain == blocked or domain.endswith("." + blocked) for blocked in EXCLUDED_DOMAINS) and _is_direct_company_result(url, title, content):
            return domain, url, content
    return None


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

    lead_results = []
    for query in _lead_queries():
        response = requests.post(
            settings.search_api_url,
            headers={"Content-Type": "application/json"},
            json={
                "api_key": settings.search_api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max(count, 5),
                "include_answer": False,
                "exclude_domains": sorted(EXCLUDED_DOMAINS - DISCOVERY_ONLY_DOMAINS),
            },
            timeout=30,
        )
        response.raise_for_status()
        lead_results.extend(response.json().get("results", []))

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
        if not _is_direct_company_result(url, title, content):
            continue
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

    # Use LinkedIn/startup-list pages only to discover a name, then resolve the
    # name to an official website before exposing it to Hunter.
    for result in lead_results:
        source_url = result.get("url", "")
        source_domain = _domain(source_url)
        if not any(source_domain == allowed or source_domain.endswith("." + allowed) for allowed in DISCOVERY_ONLY_DOMAINS):
            continue
        name = _candidate_name(result.get("title", ""))
        if not name:
            continue
        resolved = _resolve_official_website(name)
        if not resolved:
            continue
        domain, official_url, content = resolved
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        score, reason = _score(f"{name} {content}")
        companies.append(Company(name=name, website=f"https://{domain}", careers_url=official_url, description=content[:500], relevant_opening="Direct company outreach", source_url=source_url, match_score=score, match_reason=f"resolved from {source_domain} lead; {reason}"))
        if len(companies) >= count * 2:
            break

    return sorted(companies, key=lambda item: item.match_score, reverse=True)[:count]
