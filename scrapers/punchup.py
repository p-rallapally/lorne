from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from models import Event
from scrapers.base import BaseScraper


load_dotenv()


class PunchupScraper(BaseScraper):
    SUPABASE_URL = "https://xudgmlzkdlowirdrfhmw.supabase.co"

    def __init__(
        self,
        url: str,
        performer: str | None = None,
    ) -> None:
        super().__init__(url, performer)

        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError(
                "Punchup URL must begin with http:// or https://"
            )

        if parsed.hostname not in {
            "punchup.live",
            "www.punchup.live",
        }:
            raise ValueError(
                "Expected a Punchup URL such as "
                "https://punchup.live/tommybrennan"
            )

        self.slug = parsed.path.strip("/").split("/")[0]
        self.api_key = os.getenv("PUNCHUP_SUPABASE_KEY")

        if not self.api_key:
            raise RuntimeError(
                "PUNCHUP_SUPABASE_KEY is missing from .env"
            )
        

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Profile": "public",
            "User-Agent": "Scraper-Night-Live/0.4",
        }

    def fetch_comedian(self) -> dict[str, Any]:
        response = requests.get(
            f"{self.SUPABASE_URL}/rest/v1/comedians",
            headers=self._headers(),
            params={
                "slug": f"eq.{self.slug}",
                "select": "id,display_name,slug",
                "limit": "1",
            },
            timeout=30,
        )

        response.raise_for_status()
        records = response.json()

        if not records:
            raise RuntimeError(
                f"No Punchup comedian found for slug '{self.slug}'."
            )

        return records[0]
    
    def fetch_shows(
        self,
        comedian_id: str,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        response = requests.get(
            f"{self.SUPABASE_URL}/rest/v1/show_comedian_pairings",
            headers=self._headers(),
            params={
                "select": (
                    "show_id,"
                    "comedian_shows!inner("
                    "id,datetime,venue,location,ticket_link,"
                    "vip_ticket_link,is_sold_out,title"
                    ")"
                ),
                "comedian_id": f"eq.{comedian_id}",
                "comedian_shows.datetime": f"gte.{now}",
            },
            timeout=30,
        )

        response.raise_for_status()
        pairings = response.json()

        shows: list[dict[str, Any]] = []

        for pairing in pairings:
            nested_show = pairing.get("comedian_shows")

            if isinstance(nested_show, dict):
                shows.append(nested_show)

            elif isinstance(nested_show, list):
                shows.extend(
                    show
                    for show in nested_show
                    if isinstance(show, dict)
                )

        shows.sort(
            key=lambda show: show.get("datetime") or "9999-12-31"
        )

        return shows

    def parse_shows(
            self,
            shows: list[dict[str, Any]],
            performer_name: str,
        ) -> list[Event]:
            scraped_at = datetime.now(timezone.utc).isoformat()
            events: list[Event] = []

            for show in shows:
                ticket_url = (
                    show.get("ticket_link")
                    or show.get("vip_ticket_link")
                )

                venue = show.get("venue")
                title = show.get("title")

                if not venue and title:
                    venue = title

                events.append(
                    Event(
                        performer=performer_name,
                        event_id=str(show["id"]),
                        date=show.get("datetime"),
                        end_date=None,
                        venue=venue,
                        location=show.get("location"),
                        ticket_url=ticket_url,
                        sold_out=show.get("is_sold_out"),
                        source_url=self.url,
                        source_platform="punchup",
                        scraped_at=scraped_at,
                    )
                )

            return events

    def scrape(self) -> list[Event]:
            comedian = self.fetch_comedian()
            shows = self.fetch_shows(comedian["id"])

            performer_name = (
                self.performer
                or comedian.get("display_name")
                or self.slug
            )

            return self.parse_shows(
                shows=shows,
                performer_name=performer_name,
            )