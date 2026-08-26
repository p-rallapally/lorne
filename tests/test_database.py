from __future__ import annotations

import sqlite3

import database
from models import Event


def make_event(event_id: str, venue: str = "Venue") -> Event:
    return Event(
        performer="Test Performer",
        event_id=event_id,
        date="2099-01-01T00:00:00+00:00",
        end_date=None,
        venue=venue,
        location="Los Angeles, CA",
        ticket_url="https://example.com/tickets",
        sold_out=False,
        source_url="https://example.com/tour",
        source_platform="test",
        scraped_at="ignored by persistence",
    )


def use_temp_database(tmp_path, monkeypatch):
    path = tmp_path / "events.db"
    monkeypatch.setattr(database, "DATABASE_FILE", path)
    database.initialize_database()
    return path


def test_sync_preserves_history_and_coordinates(tmp_path, monkeypatch) -> None:
    path = use_temp_database(tmp_path, monkeypatch)
    first = database.sync_performer_events(
        "Test Performer", [make_event("one"), make_event("two")]
    )
    assert first == database.SyncResult(new=2, existing=0, removed=0)

    with sqlite3.connect(path) as connection:
        initial = connection.execute(
            "SELECT first_seen, last_seen FROM events WHERE event_id = 'one'"
        ).fetchone()
        connection.execute("ALTER TABLE events ADD COLUMN latitude REAL")
        connection.execute("ALTER TABLE events ADD COLUMN longitude REAL")
        connection.execute(
            "UPDATE events SET latitude = 34.05, longitude = -118.24 "
            "WHERE event_id = 'one'"
        )

    monkeypatch.setattr(database, "_now", lambda: "2026-01-02T00:00:00+00:00")
    second = database.sync_performer_events(
        "Test Performer", [make_event("one", venue="Updated Venue")]
    )
    assert second == database.SyncResult(new=0, existing=1, removed=1)

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        one = connection.execute(
            "SELECT * FROM events WHERE event_id = 'one'"
        ).fetchone()
        two = connection.execute(
            "SELECT active FROM events WHERE event_id = 'two'"
        ).fetchone()

    assert one["first_seen"] == initial[0]
    assert one["last_seen"] == "2026-01-02T00:00:00+00:00"
    assert one["active"] == 1
    assert (one["latitude"], one["longitude"]) == (34.05, -118.24)
    assert two["active"] == 0


def test_initialize_migrates_an_existing_database(tmp_path, monkeypatch) -> None:
    path = tmp_path / "events.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE events (
                performer TEXT NOT NULL, event_id TEXT NOT NULL, date TEXT,
                end_date TEXT, venue TEXT, location TEXT, ticket_url TEXT,
                sold_out INTEGER, source_url TEXT NOT NULL,
                source_platform TEXT NOT NULL,
                PRIMARY KEY (source_platform, event_id)
            )
            """
        )
        connection.execute(
            "INSERT INTO events (performer, event_id, source_url, source_platform) "
            "VALUES ('Test Performer', 'old', 'https://example.com', 'test')"
        )

    monkeypatch.setattr(database, "DATABASE_FILE", path)
    database.initialize_database()

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT first_seen, last_seen, active FROM events"
        ).fetchone()
    assert row[0] is not None
    assert row[1] is not None
    assert row[2] == 1


def test_scrape_run_summary(tmp_path, monkeypatch) -> None:
    path = use_temp_database(tmp_path, monkeypatch)
    database.sync_performer_events("Test Performer", [make_event("one")])

    monkeypatch.setattr(database, "_now", lambda: "2026-01-01T00:00:00+00:00")
    run_id = database.begin_scrape_run()
    monkeypatch.setattr(database, "_now", lambda: "2026-01-01T00:01:00+00:00")
    summary = database.finish_scrape_run(run_id, total_new=1, total_removed=2)

    assert summary["started_at"] == "2026-01-01T00:00:00+00:00"
    assert summary["finished_at"] == "2026-01-01T00:01:00+00:00"
    assert summary["total_new"] == 1
    assert summary["total_removed"] == 2
    assert summary["total_active"] == 1
    assert database.latest_scrape_run()["run_id"] == run_id
