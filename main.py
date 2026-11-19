"""Command-line entry point for the first MVP slice."""

import argparse

from config import settings
from services.company_finder import discover_companies
from services.tracker import Tracker


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover internship companies and track them locally.")
    parser.add_argument("--count", type=int, default=10, help="number of companies to keep")
    args = parser.parse_args()

    tracker = Tracker(settings.database_path)
    try:
        companies = discover_companies(max(1, min(args.count, 50)))
    except RuntimeError as error:
        print(f"Setup needed: {error}")
        return
    for company in companies:
        tracker.save_company(company)
        print(f"{company.match_score:>3}  {company.name}  {company.careers_url}")
    print(f"\nSaved {len(companies)} companies to {settings.database_path}")
    tracker.close()


if __name__ == "__main__":
    main()
