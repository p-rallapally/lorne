from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from models import Event


ROOT = Path(__file__).parent
DATABASE_FILE = ROOT / "data" / "events.db"


@dataclass(frozen=True)
class SyncResult:
    new: int
    existing: int
    removed: int


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
                end_date TEXT,
                venue TEXT,
                location TEXT,
                ticket_url TEXT,
                sold_out INTEGER,
                source_url TEXT NOT NULL,
                source_platform TEXT NOT NULL,
                first_seen TEXT,
                last_seen TEXT,
                active INTEGER NOT NULL DEFAULT 1,

                PRIMARY KEY (source_platform, event_id)
            )
            """
        )

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(events)")
        }
        if "first_seen" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN first_seen TEXT")
        if "last_seen" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN last_seen TEXT")
        if "active" not in columns:
            connection.execute(
                "ALTER TABLE events ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
            )

        # Rows created before history tracking have no true first-seen time.
        # Migration time is the safest available approximation.
        now = _now()
        connection.execute(
            "UPDATE events SET first_seen = ? WHERE first_seen IS NULL", (now,)
        )
        connection.execute(
            "UPDATE events SET last_seen = ? WHERE last_seen IS NULL", (now,)
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scrape_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                total_new INTEGER NOT NULL DEFAULT 0,
                total_removed INTEGER NOT NULL DEFAULT 0,
                total_active INTEGER
            )
            """
        )


def begin_scrape_run() -> int:
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO scrape_runs (started_at) VALUES (?)",
            (_now(),),
        )
        return cursor.lastrowid


def finish_scrape_run(
    run_id: int,
    total_new: int,
    total_removed: int,
) -> sqlite3.Row:
    with connect() as connection:
        total_active = connection.execute(
            "SELECT COUNT(*) FROM events WHERE active = 1"
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE scrape_runs
            SET finished_at = ?, total_new = ?, total_removed = ?, total_active = ?
            WHERE run_id = ?
            """,
            (_now(), total_new, total_removed, total_active, run_id),
        )
        row = connection.execute(
            "SELECT * FROM scrape_runs WHERE run_id = ?", (run_id,)
        ).fetchone()

    if row is None:
        raise ValueError(f"Unknown scrape run: {run_id}")
    return row


def latest_scrape_run() -> sqlite3.Row | None:
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM scrape_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()


def active_events() -> list[sqlite3.Row]:
    """Return the events currently available to the web application."""
    with connect() as connection:
        return connection.execute(
            """
            SELECT performer, date, venue, location, ticket_url, sold_out
            FROM events
            WHERE active = 1
            ORDER BY date, performer
            """
        ).fetchall()


def upsert_events(events: list[Event]) -> None:
    with connect() as connection:
        _upsert_events(connection, events, _now())


def sync_performer_events(
    performer: str,
    events: list[Event],
) -> SyncResult:
    """Store one successful scrape and deactivate events it did not return."""
    if any(event.performer != performer for event in events):
        raise ValueError("All synced events must belong to the requested performer")

    returned_keys = {
        (event.source_platform, event.event_id)
        for event in events
    }

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT source_platform, event_id, active
            FROM events
            WHERE performer = ?
            """,
            (performer,),
        ).fetchall()
        existing = {
            (row["source_platform"], row["event_id"]): row["active"]
            for row in rows
        }
        new_count = sum(key not in existing for key in returned_keys)
        removed_count = sum(
            bool(active) and key not in returned_keys
            for key, active in existing.items()
        )

        connection.execute(
            "UPDATE events SET active = 0 WHERE performer = ?", (performer,)
        )
        _upsert_events(connection, events, _now())

    return SyncResult(
        new=new_count,
        existing=len(returned_keys) - new_count,
        removed=removed_count,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_events(
    connection: sqlite3.Connection,
    events: list[Event],
    seen_at: str,
) -> None:
    for event in events:
        connection.execute(
            """
            INSERT INTO events (
                performer,
                event_id,
                date,
                end_date,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)

            ON CONFLICT(source_platform, event_id)
            DO UPDATE SET
                performer = excluded.performer,
                date = excluded.date,
                end_date = excluded.end_date,
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
                event.end_date,
                event.venue,
                event.location,
                event.ticket_url,
                int(event.sold_out) if event.sold_out is not None else None,
                event.source_url,
                event.source_platform,
                seen_at,
                seen_at,
            ),
        )
