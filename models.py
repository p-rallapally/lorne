from dataclasses import dataclass


@dataclass
class Event:
    performer: str
    event_id: str | None
    date: str | None
    venue: str | None
    location: str | None
    ticket_url: str | None
    sold_out: bool | None
    source_url: str
    source_platform: str
    scraped_at: str