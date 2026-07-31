from dataclasses import dataclass


@dataclass
class Event:
    performer: str
    date: str
    venue: str
    location: str
    ticket_url: str