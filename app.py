from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import initialize_database, performer_names
from search import search_events


ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=ROOT / "templates")

app = FastAPI(title="Lorne Events API")
initialize_database()


def event_results(
    performer: str | None,
    location: str | None,
    radius: float | None,
    start_date: date | None,
    end_date: date | None,
    sort: Literal["date_asc", "date_desc", "performer"],
) -> list[dict]:
    if radius is not None and not location:
        raise HTTPException(400, "location is required when radius is provided")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "start_date cannot be after end_date")

    try:
        rows = search_events(
            performer=performer,
            location=None if radius is not None else location,
            after=start_date.isoformat() if start_date else None,
            before=end_date.isoformat() if end_date else None,
            near=location if radius is not None else None,
            radius=radius or 100,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

    events = []
    for result in rows:
        row, distance = result if isinstance(result, tuple) else (result, None)
        event = dict(row)
        event["sold_out"] = (
            bool(event["sold_out"]) if event["sold_out"] is not None else None
        )
        event["details_url"] = event["ticket_url"] or event["source_url"]
        event["distance_miles"] = round(distance, 1) if distance is not None else None
        events.append(event)

    if sort == "date_desc":
        events.reverse()
    elif sort == "performer":
        events.sort(
            key=lambda event: (
                event["performer"].lower(),
                event["date"] or "9999-12-31",
            )
        )
    return events


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/events")
def events(
    performer: str | None = None,
    location: str | None = None,
    radius: float | None = Query(default=None, gt=0, le=1000),
    start_date: date | None = None,
    end_date: date | None = None,
    sort: Literal["date_asc", "date_desc", "performer"] = "date_asc",
):
    return event_results(performer, location, radius, start_date, end_date, sort)


@app.get("/search")
def search(
    performer: str | None = None,
    location: str | None = None,
    radius: float | None = Query(default=None, gt=0, le=1000),
    start_date: date | None = None,
    end_date: date | None = None,
    sort: Literal["date_asc", "date_desc", "performer"] = "date_asc",
):
    return event_results(performer, location, radius, start_date, end_date, sort)


@app.get("/performers")
def performers():
    return performer_names()
