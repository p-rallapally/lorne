import requests

URL = "https://i.komi.io/profiles/v1/published"


def extract_event_items(payload: dict) -> list[dict]:
    data = payload.get("data", {})
    modules = data.get("modules", [])

    events = []

    for module in modules:
        if module.get("type") == "EVENTS":
            events.extend(module.get("items", []))

    return events

from datetime import datetime


def normalize_event(event: dict, performer: str) -> dict:
    raw_location = event.get("location", "").strip(" ,")

    city = None
    region = None

    if "," in raw_location:
        parts = [part.strip() for part in raw_location.split(",") if part.strip()]
        city = parts[0] if parts else None
        region = parts[1] if len(parts) > 1 else None

    raw_date = event.get("eventDate")
    event_date = (
        datetime.fromisoformat(raw_date).date().isoformat()
        if raw_date
        else None
    )

    return {
        "source_event_id": event.get("id"),
        "performer": performer,
        "date": event_date,
        "venue": event.get("venueName"),
        "location_raw": raw_location,
        "city": city,
        "region": region,
        "ticket_url": (
            event.get("url")
            or event.get("ticketUrl")
            or event.get("link")
        ),
        "source_platform": "komi",
    }