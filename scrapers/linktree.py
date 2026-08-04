from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from models import Event
from scrapers.base import BaseScraper


MONTHS = {
    "JAN": 1,
    "JANUARY": 1,
    "FEB": 2,
    "FEBRUARY": 2,
    "MAR": 3,
    "MARCH": 3,
    "APR": 4,
    "APRIL": 4,
    "MAY": 5,
    "JUN": 6,
    "JUNE": 6,
    "JUL": 7,
    "JULY": 7,
    "AUG": 8,
    "AUGUST": 8,
    "SEP": 9,
    "SEPT": 9,
    "SEPTEMBER": 9,
    "OCT": 10,
    "OCTOBER": 10,
    "NOV": 11,
    "NOVEMBER": 11,
    "DEC": 12,
    "DECEMBER": 12,
}


class LinktreeScraper(BaseScraper):
    def __init__(
        self,
        url: str,
        performer: str | None = None,
    ) -> None:
        super().__init__(url, performer)

        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Linktree URL must begin with http:// or https://")

        if parsed.hostname not in {"linktr.ee", "www.linktr.ee"}:
            raise ValueError(
                "Expected a Linktree URL such as https://linktr.ee/jajcenter"
            )

    def fetch_html(self) -> str:
        response = requests.get(
            self.url,
            headers={
                "User-Agent": "Scraper-Night-Live/0.1",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=30,
        )

        response.raise_for_status()
        return response.text

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None

        text = re.sub(r"\s+", " ", str(value)).strip()
        return text or None

    @staticmethod
    def _looks_like_event(text: str) -> bool:
        upper = text.upper()

        contains_month = any(
            re.search(rf"\b{re.escape(month)}\b", upper)
            for month in MONTHS
        )

        # Most US tour listings include a two-letter state abbreviation.
        contains_state = bool(
            re.search(r"\b[A-Z]{2}\b", upper)
        )

        return contains_month and contains_state

    @staticmethod
    def _extract_dates(
        text: str,
        default_year: int,
    ) -> tuple[str | None, str | None]:
        """
        Supports common Linktree labels such as:

        AUGUST 13
        AUGUST 14-15
        JULY 30-AUG 01
        JULY 09-11
        """

        upper = text.upper()

        month_pattern = "|".join(
            sorted(MONTHS, key=len, reverse=True)
        )

        match = re.search(
            rf"\b({month_pattern})\s+"
            rf"(\d{{1,2}})"
            rf"(?:\s*-\s*(?:({month_pattern})\s+)?(\d{{1,2}}))?",
            upper,
        )

        if not match:
            return None, None

        start_month_text = match.group(1)
        start_day = int(match.group(2))
        end_month_text = match.group(3)
        end_day_text = match.group(4)

        start_month = MONTHS[start_month_text]

        try:
            start = datetime(
                default_year,
                start_month,
                start_day,
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None, None

        end = None

        if end_day_text:
            end_month = (
                MONTHS[end_month_text]
                if end_month_text
                else start_month
            )

            end_year = default_year

            # Handles a range that crosses December into January.
            if end_month < start_month:
                end_year += 1

            try:
                end = datetime(
                    end_year,
                    end_month,
                    int(end_day_text),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                end = None

        return (
            start.isoformat(),
            end.isoformat() if end else None,
        )

    @staticmethod
    def _extract_location(text: str) -> str | None:
        """
        Find common CITY, ST or CITY ST patterns.
        """

        upper = text.upper()

        # Examples:
        # INDIANAPOLIS, IN
        # PITTSBURGH PA
        # RICHMOND HEIGHTS, MO
        matches = list(
            re.finditer(
                r"\b([A-Z][A-Z .'-]+?),?\s+([A-Z]{2})\b",
                upper,
            )
        )

        if not matches:
            return None

        match = matches[-1]
        city = match.group(1).strip(" ,-")
        state = match.group(2)

        # Remove leading date fragments accidentally captured as part of city.
        city = re.sub(
            r"^(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|"
            r"APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|"
            r"AUG(?:UST)?|SEP(?:T(?:EMBER)?)?|OCT(?:OBER)?|"
            r"NOV(?:EMBER)?|DEC(?:EMBER)?)"
            r"\s+\d{1,2}(?:-\d{1,2})?\s*[-–—]?\s*",
            "",
            city,
        ).strip()

        return f"{city.title()}, {state}" if city else None

    @staticmethod
    def _make_event_id(
        performer: str,
        date: str | None,
        label: str,
        ticket_url: str,
    ) -> str:
        raw = "|".join(
            [
                performer,
                date or "",
                label,
                ticket_url,
            ]
        )

        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def parse_events(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")

        performer = self.performer or self.url.rstrip("/").split("/")[-1]
        current_year = datetime.now(timezone.utc).year
        scraped_at = datetime.now(timezone.utc).isoformat()

        events: list[Event] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            label = self._clean_text(anchor.get_text(" ", strip=True))
            href = urljoin(self.url, anchor["href"])

            if not label or not self._looks_like_event(label):
                continue

            # Ignore Linktree's own navigation/profile links.
            hostname = urlparse(href).hostname or ""

            if hostname.endswith("linktr.ee"):
                continue

            start_date, end_date = self._extract_dates(
                label,
                default_year=current_year,
            )

            if not start_date:
                continue

            location = self._extract_location(label)

            event_id = self._make_event_id(
                performer=performer,
                date=start_date,
                label=label,
                ticket_url=href,
            )

            if event_id in seen:
                continue

            seen.add(event_id)

            events.append(
                Event(
                    performer=performer,
                    event_id=event_id,
                    date=start_date,
                    end_date=end_date,
                    venue=label,
                    location=location,
                    ticket_url=href,
                    sold_out=None,
                    source_url=self.url,
                    source_platform="linktree",
                    scraped_at=scraped_at,
                )
            )

        return events

    def scrape(self) -> list[Event]:
        html = self.fetch_html()
        return self.parse_events(html)