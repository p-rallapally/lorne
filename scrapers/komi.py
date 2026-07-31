from __future__ import annotations
from pprint import pprint
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse
import re

import requests


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


class KomiScraper:
    API_URL = "https://i.komi.io/profiles/v1/published"

    @staticmethod
    def _bandsintown_id_from_url(url: str | None) -> str | None:
        if not url:
            return None

        match = re.search(r"/t/(\d+)", url)

        if match:
            return match.group(1)

        return None

    def __init__(self, tour_page_url: str) -> None:
        self.tour_page_url = tour_page_url.rstrip("/") + "/"

        parsed = urlparse(self.tour_page_url)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError(
                "Tour page URL must begin with http:// or https://"
            )

        if not parsed.hostname or not parsed.hostname.endswith(".komi.io"):
            raise ValueError(
                "Expected a Komi page such as "
                "https://sarahsquirm.komi.io/"
            )

        self.origin = f"{parsed.scheme}://{parsed.hostname}"
        self.handle = parsed.hostname.removesuffix(".komi.io")

    def fetch_profile(self) -> dict[str, Any]:
        """Download the public Komi profile JSON."""

        headers = {
            "Accept": "application/json",
            "Origin": self.origin,
            "Referer": self.tour_page_url,
            "x-service-name": "consumer",
            "User-Agent": "SNL-Tour-Tracker/0.1",
        }

        response = requests.get(
            self.API_URL,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise RuntimeError(
                "Komi returned a response that was not valid JSON."
            ) from exc

        if not payload.get("success"):
            raise RuntimeError("Komi returned success=false.")

        return payload

    def _find_event_modules(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:
        """Recursively locate objects whose type is EVENTS."""

        found: list[dict[str, Any]] = []

        if isinstance(value, dict):
            if value.get("type") == "EVENTS":
                found.append(value)

            for child in value.values():
                found.extend(self._find_event_modules(child))

        elif isinstance(value, list):
            for child in value:
                found.extend(self._find_event_modules(child))

        return found

    def _find_items_by_type(
        self,
        value: Any,
        target_type: str,
    ) -> list[dict[str, Any]]:
        """Recursively locate objects matching a given type."""

        found: list[dict[str, Any]] = []

        if isinstance(value, dict):
            current_type = str(value.get("type", "")).lower()

            if current_type == target_type.lower():
                found.append(value)

            for child in value.values():
                found.extend(
                    self._find_items_by_type(child, target_type)
                )

        elif isinstance(value, list):
            for child in value:
                found.extend(
                    self._find_items_by_type(child, target_type)
                )

        return found

    @staticmethod
    def _first_present(
        item: dict[str, Any],
        *keys: str,
    ) -> Any:
        """Return the first nonempty value among possible field names."""

        for key in keys:
            value = item.get(key)

            if value not in (None, ""):
                return value

        return None

    def _normalize_event_item(
        self,
        item: dict[str, Any],
        performer: str,
        source_platform: str,
    ) -> Event | None:
        if source_platform == "bandsintown":
            event_id = self._first_present(
                item,
                "bandsintownEventId",
                "eventId",
                "event_id",
                "artist_event_id",
            )
        else:
            event_id = self._first_present(
                item,
                "id",
                "eventId",
                "event_id",
            )

        date = self._first_present(
            item,
            "eventDate",
            "datetime",
            "date",
            "startDate",
        )

        venue_value = self._first_present(
            item,
            "venueName",
            "venue",
            "title",
            "name",
        )

        location_value = self._first_present(
            item,
            "location",
            "formattedLocation",
            "description",
            "city",
                )

        if isinstance(venue_value, dict):
            venue = self._first_present(
                venue_value,
                "name",
                "venueName",
                "title",
            )

            if not location_value:
                city = self._first_present(
                    venue_value,
                    "city",
                    "location",
                )

                region = self._first_present(
                    venue_value,
                    "region",
                    "state",
                )

                country = self._first_present(
                    venue_value,
                    "country",
                )

                location_parts = [
                    str(value)
                    for value in [city, region, country]
                    if value not in (None, "")
                ]

                location_value = ", ".join(location_parts) or None
        else:
            venue = venue_value

        if isinstance(location_value, dict):
            city = self._first_present(
                location_value,
                "city",
                "name",
            )

            region = self._first_present(
                location_value,
                "region",
                "state",
            )

            country = self._first_present(
                location_value,
                "country",
            )

            location_parts = [
                str(value)
                for value in [city, region, country]
                if value not in (None, "")
            ]

            location = ", ".join(location_parts) or None
        else:
            location = location_value

        ticket_url = self._first_present(
            item,
            "url",
            "ticketUrl",
            "ticketURL",
            "offersUrl",
            "href",
            "link",
        )

        if source_platform == "bandsintown":
            event_id = (
                self._first_present(
                    item,
                    "bandsintownEventId",
                    "eventId",
                    "event_id",
                    "artist_event_id",
                )
                or self._bandsintown_id_from_url(ticket_url)
    )
        else:
            event_id = self._first_present(
                item,
                "id",
                "eventId",
                "event_id",
            )

        sold_out = self._first_present(
            item,
            "soldOut",
            "isSoldOut",
        )

        if not any([date, venue, location, ticket_url]):
            return None

        # The generic Bandsintown "id" may be the same module ID for every
        # event, so construct a stable fallback identifier.
        if event_id is None:
            event_id = "|".join(
                str(value)
                for value in [date, venue, location, ticket_url]
                if value not in (None, "")
            )

        return Event(
            performer=performer,
            event_id=str(event_id) if event_id else None,
            date=str(date) if date is not None else None,
            venue=str(venue) if venue is not None else None,
            location=str(location) if location is not None else None,
            ticket_url=(
                str(ticket_url)
                if ticket_url is not None
                else None
            ),
            sold_out=(
                sold_out
                if isinstance(sold_out, bool)
                else None
            ),
            source_url=self.tour_page_url,
            source_platform=source_platform,
        )

    def parse_events(
        self,
        payload: dict[str, Any],
    ) -> list[Event]:
        data = payload.get("data", {})

        performer = (
            data.get("profileInfo", {}).get("name")
            or data.get("handle")
            or self.handle
        )

        events: list[Event] = []
        seen_ids: set[str] = set()

        # Komi-native event modules.
        event_modules = self._find_event_modules(data)

        for module in event_modules:
            for item in module.get("items", []):
                if not isinstance(item, dict):
                    continue

                event = self._normalize_event_item(
                    item=item,
                    performer=performer,
                    source_platform="komi",
                )

                if event is None:
                    continue

                if event.event_id and event.event_id in seen_ids:
                    continue

                if event.event_id:
                    seen_ids.add(event.event_id)

                events.append(event)

        # Bandsintown events stored in asyncData.
        bandsintown_items = self._find_items_by_type(
            data.get("asyncData", {}),
            "bandsintown",
        )

        for item in bandsintown_items:
            event = self._normalize_event_item(
                item=item,
                performer=performer,
                source_platform="bandsintown",
            )

            if event is None:
                continue

            if event.event_id and event.event_id in seen_ids:
                continue

            if event.event_id:
                seen_ids.add(event.event_id)

            events.append(event)

        return events

    def scrape(self) -> list[Event]:
        payload = self.fetch_profile()
        return self.parse_events(payload)


def main() -> None:
    scraper = KomiScraper(
        "https://michaellongfellow.komi.io/"
    )

    events = scraper.scrape()

    print(f"Found {len(events)} events.\n")

    for event in events:
        print(asdict(event))


def main() -> None:
    urls = [
        "https://sarahsquirm.komi.io/",
        "https://michaellongfellow.komi.io/",
    ]

    for url in urls:
        scraper = KomiScraper(url)
        events = scraper.scrape()

        print(f"\n{url}")
        print(f"Found {len(events)} events.\n")

        for event in events:
            print(asdict(event))




if __name__ == "__main__":
    main()
