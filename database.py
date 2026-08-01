from __future__ import annotations

import sqlite3
from pathlib import Path

from models import Event


ROOT = Path(__file__).parent
DATABASE_FILE = ROOT / "data" / "events.db"


def connect() -> sqlite3.Connection:
    DATABASE_FILE.parent.mkdir(exist_ok=True)

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                performer TEXT NOT NULL,
                event_id TEXT NOT NULL,
                date TEXT,
                venue TEXT,
                location TEXT,
                ticket_url TEXT,
                sold_out INTEGER,
                source_url TEXT NOT NULL,
                source_platform TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,

                PRIMARY KEY (source_platform, event_id)
            )
            """
        )


def upsert_events(events: list[Event]) -> None:
    with connect() as connection:
        for event in events:
            connection.execute(
                """
                INSERT INTO events (
                    performer,
                    event_id,
                    date,
                    venue,
                    location,
                    ticket_url,
                    sold_out,
                    source_url,
                    source_platform,
                    first_seen,
                    last_seen,
                    active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)

                ON CONFLICT(source_platform, event_id)
                DO UPDATE SET
                    performer = excluded.performer,
                    date = excluded.date,
                    venue = excluded.venue,
                    location = excluded.location,
                    ticket_url = excluded.ticket_url,
                    sold_out = excluded.sold_out,
                    source_url = excluded.source_url,
                    last_seen = excluded.last_seen,
                    active = 1
                """,
                (
                    event.performer,
                    event.event_id,
                    event.date,
                    event.venue,
                    event.location,
                    event.ticket_url,
                    int(event.sold_out)
                    if event.sold_out is not None
                    else None,
                    event.source_url,
                    event.source_platform,
                    event.scraped_at,
                    event.scraped_at,
                ),
            )