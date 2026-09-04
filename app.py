"""Lorne web application.

Serves a small JSON API over the events database (built on top of the
existing search.py / database.py logic) plus the static frontend that
consumes it. Replaces the previous Flask app.

Local dev:
    uvicorn app:app --reload

Production (Render):
    gunicorn -k uvicorn.workers.UvicornWorker app:app
"""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import connect, initialize_database
from geocode import initialize_geocoding_schema
from search import distance_miles, geocode_search_location, validate_date

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"

SortOption = Literal["date_asc", "date_desc", "performer", "distance"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Same setup the old Flask app did on import, plus the geocoding
    # migration (adds latitude/longitude columns if they're missing).
    initialize_database()
    initialize_geocoding_schema()
    yield


app = FastAPI(
    title="Lorne",
    description="Find upcoming live performances by current and former SNL cast members.",
    lifespan=lifespan,
)

# Wide open on purpose: this is a public, read-only GET API with no
# credentials or user data, so there's no origin to protect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class EventOut(BaseModel):
    performer: str
    date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = None
    location: Optional[str] = None
    ticket_url: Optional[str] = None
    sold_out: Optional[bool] = None
    source_url: str
    distance_miles: Optional[float] = None


class EventsResponse(BaseModel):
    count: int
    events: list[EventOut]


class PerformerOut(BaseModel):
    performer: str
    upcoming_count: int


class PerformersResponse(BaseModel):
    count: int
    performers: list[PerformerOut]


# ---------------------------------------------------------------------------
# Shared query logic (mirrors search.py's filtering, extended with `q` and
# API-friendly sorting/pagination; search.py itself is left untouched so the
# `python search.py --near ...` CLI keeps working as-is)
# ---------------------------------------------------------------------------


def _fetch_events(
    performer: Optional[str],
    location: Optional[str],
    q: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    include_all: bool,
) -> list[sqlite3.Row]:
    conditions: list[str] = []
    parameters: list[str] = []

    if performer:
        conditions.append("LOWER(performer) LIKE LOWER(?)")
        parameters.append(f"%{performer}%")

    if location:
        # Scrapers do not use one consistent location format. For example,
        # the UI may send "Dallas, TX" while an event stores
        # "Dallas, United States". Match both the complete input and its city
        # portion, and include venue names as a fallback.
        full_location = f"%{location.strip()}%"
        city = location.split(",", 1)[0].strip()
        city_location = f"%{city}%"
        conditions.append(
            "(LOWER(location) LIKE LOWER(?) "
            "OR LOWER(venue) LIKE LOWER(?) "
            "OR LOWER(location) LIKE LOWER(?) "
            "OR LOWER(venue) LIKE LOWER(?))"
        )
        parameters.extend(
            [full_location, full_location, city_location, city_location]
        )

    if q:
        conditions.append(
            "(LOWER(performer) LIKE LOWER(?) "
            "OR LOWER(venue) LIKE LOWER(?) "
            "OR LOWER(location) LIKE LOWER(?))"
        )
        like = f"%{q}%"
        parameters.extend([like, like, like])

    if start_date:
        conditions.append("DATE(date) >= DATE(?)")
        parameters.append(start_date)

    if end_date:
        conditions.append("DATE(date) <= DATE(?)")
        parameters.append(end_date)

    if not include_all:
        conditions.append("DATE(date) >= DATE('now')")
        conditions.append("active = 1")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT
            performer, event_id, date, end_date, venue, location,
            ticket_url, sold_out, source_url, source_platform,
            latitude, longitude
        FROM events
        {where_clause}
        ORDER BY DATE(date), performer, venue
    """

    with connect() as connection:
        return connection.execute(query, parameters).fetchall()


def _apply_near_and_sort(
    rows: list[sqlite3.Row],
    near: Optional[str],
    radius: float,
    sort: SortOption,
) -> list[EventOut]:
    distances: dict[tuple[str, str], float] = {}

    if near:
        try:
            search_lat, search_lon = geocode_search_location(near)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        filtered = []
        for row in rows:
            lat, lon = row["latitude"], row["longitude"]
            if lat is None or lon is None:
                continue
            distance = distance_miles(search_lat, search_lon, lat, lon)
            if distance <= radius:
                distances[(row["source_platform"], row["event_id"])] = distance
                filtered.append(row)
        rows = filtered

    events = [
        EventOut(
            performer=row["performer"],
            date=row["date"],
            end_date=row["end_date"],
            venue=row["venue"],
            location=row["location"],
            ticket_url=row["ticket_url"] or row["source_url"],
            sold_out=bool(row["sold_out"]) if row["sold_out"] is not None else None,
            source_url=row["source_url"],
            distance_miles=distances.get((row["source_platform"], row["event_id"])),
        )
        for row in rows
    ]

    if sort == "distance" and near:
        events.sort(
            key=lambda e: e.distance_miles if e.distance_miles is not None else float("inf")
        )
    elif sort == "performer":
        events.sort(key=lambda e: (e.performer.lower(), e.date or "9999-12-31"))
    elif sort == "date_desc":
        events.sort(key=lambda e: (e.date or "0000-01-01"), reverse=True)
    else:  # date_asc, or "distance" requested without `near`
        events.sort(key=lambda e: (e.date or "9999-12-31", e.performer.lower()))

    return events


def _validate_dates(
    start_date: Optional[str], end_date: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    try:
        return (
            validate_date(start_date, "start_date"),
            validate_date(end_date, "end_date"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.get("/api/events", response_model=EventsResponse)
def list_events(
    performer: Optional[str] = Query(None, description="Filter by performer name (substring match)."),
    location: Optional[str] = Query(None, description="Filter by location text (substring match)."),
    q: Optional[str] = Query(None, description="Free-text search across performer, venue, and location."),
    near: Optional[str] = Query(None, description="City/address to search near, e.g. 'Santa Barbara, CA'."),
    radius: float = Query(100, gt=0, le=5000, description="Radius in miles, used together with `near`."),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD, only events on/after this date."),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD, only events on/before this date."),
    sort: SortOption = Query("date_asc"),
    include_all: bool = Query(False, description="Include past and inactive events."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> EventsResponse:
    start_date, end_date = _validate_dates(start_date, end_date)

    try:
        rows = _fetch_events(performer, location, q, start_date, end_date, include_all)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    events = _apply_near_and_sort(rows, near, radius, sort)
    page = events[offset : offset + limit]
    return EventsResponse(count=len(events), events=page)


@app.get("/api/search", response_model=EventsResponse)
def search_events_endpoint(
    q: str = Query(..., min_length=1, description="Free-text search across performer, venue, and location."),
    near: Optional[str] = Query(None),
    radius: float = Query(100, gt=0, le=5000),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort: SortOption = Query("date_asc"),
    include_all: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> EventsResponse:
    """Thin, explicit alias of /api/events for a single free-text query."""
    return list_events(
        performer=None,
        location=None,
        q=q,
        near=near,
        radius=radius,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
        include_all=include_all,
        limit=limit,
        offset=offset,
    )


@app.get("/api/performers", response_model=PerformersResponse)
def list_performers(
    include_all: bool = Query(False, description="Include performers with no upcoming events."),
) -> PerformersResponse:
    condition = "" if include_all else "WHERE active = 1 AND DATE(date) >= DATE('now')"
    query = f"""
        SELECT performer, COUNT(*) AS upcoming_count
        FROM events
        {condition}
        GROUP BY performer
        ORDER BY performer
    """
    with connect() as connection:
        rows = connection.execute(query).fetchall()

    performers = [
        PerformerOut(performer=row["performer"], upcoming_count=row["upcoming_count"])
        for row in rows
    ]
    return PerformersResponse(count=len(performers), performers=performers)


# ---------------------------------------------------------------------------
# Frontend (static files)
# ---------------------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
