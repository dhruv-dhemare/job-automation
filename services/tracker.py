"""Minimal local tracker. It is intentionally replaceable by Google Sheets later."""

import sqlite3
from pathlib import Path

from services.company_finder import Company


class Tracker:
    def __init__(self, database_path: Path):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                website TEXT NOT NULL UNIQUE,
                careers_url TEXT,
                description TEXT,
                relevant_opening TEXT,
                source_url TEXT,
                match_score INTEGER,
                match_reason TEXT,
                compensation TEXT,
                compensation_source TEXT,
                status TEXT NOT NULL DEFAULT 'Discovered',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self.connection.commit()

    def save_company(self, company: Company) -> None:
        values = company.to_dict()
        self.connection.execute(
            """INSERT INTO companies
            (name, website, careers_url, description, relevant_opening, source_url,
             match_score, match_reason, compensation, compensation_source)
            VALUES (:name, :website, :careers_url, :description, :relevant_opening,
                    :source_url, :match_score, :match_reason, :compensation,
                    :compensation_source)
            ON CONFLICT(website) DO UPDATE SET
                name=excluded.name, careers_url=excluded.careers_url,
                description=excluded.description, relevant_opening=excluded.relevant_opening,
                source_url=excluded.source_url, match_score=excluded.match_score,
                match_reason=excluded.match_reason, compensation=excluded.compensation,
                compensation_source=excluded.compensation_source""",
            values,
        )
        self.connection.commit()

    def list_companies(self) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM companies ORDER BY match_score DESC"))

    def close(self) -> None:
        self.connection.close()
