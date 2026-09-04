import sqlite3

import pytest
from fastapi import HTTPException

import app


@pytest.fixture
def event_database(tmp_path, monkeypatch) -> None:
    path = tmp_path / "events.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE events (
                performer TEXT, event_id TEXT, date TEXT, end_date TEXT,
                venue TEXT, location TEXT, ticket_url TEXT, sold_out INTEGER,
                source_url TEXT, source_platform TEXT, latitude REAL,
                longitude REAL, active INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO events VALUES (
                'Michael Longfellow', 'dallas', '2099-11-12', NULL,
                'Dallas Comedy Club', 'Dallas, United States',
                'https://example.com/tickets', 0, 'https://example.com',
                'test', 32.78, -96.80, 1
            )
            """
        )

    def connect():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(app, "connect", connect)


def test_location_filter_accepts_city_or_city_and_state(event_database) -> None:
    assert len(app._fetch_events(None, "Dallas", None, None, None, False)) == 1
    assert len(app._fetch_events(None, "Dallas, TX", None, None, None, False)) == 1


@pytest.mark.parametrize(
    "query", ["Michael Longfellow", "Dallas Comedy Club", "Dallas"]
)
def test_text_search_finds_performer_venue_and_city(
    event_database, query
) -> None:
    assert app._fetch_events(None, None, query, None, None, False)


def test_rejects_reversed_date_range() -> None:
    with pytest.raises(HTTPException, match="cannot be after") as error:
        app._validate_dates("2026-12-01", "2026-01-01")
    assert error.value.status_code == 400


def test_radius_filter_and_distance_sort(event_database, monkeypatch) -> None:
    rows = app._fetch_events(None, None, None, None, None, False)
    monkeypatch.setattr(
        app, "geocode_search_location", lambda location: (32.78, -96.80)
    )
    events = app._apply_near_and_sort(rows, "Dallas, TX", 25, "distance")
    assert len(events) == 1
    assert events[0].distance_miles == pytest.approx(0)
    assert events[0].cast_status == "alumni"


def test_performer_view_data(event_database) -> None:
    response = app.list_performers(include_all=False)
    assert response.count == 1
    assert response.performers[0].performer == "Michael Longfellow"
    assert response.performers[0].cast_status == "alumni"
    assert response.performers[0].upcoming_count == 1


def test_cast_status_metadata_matches_performer_configuration() -> None:
    assert app.CAST_STATUSES == {
        "Sarah Sherman": "current",
        "Michael Longfellow": "alumni",
        "Devon Walker": "alumni",
        "James Austin Johnson": "current",
        "Andrew Dismukes": "current",
        "Emil Wakim": "alumni",
        "Tommy Brennan": "current",
    }
