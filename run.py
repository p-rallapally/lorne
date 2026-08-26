from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from changes import format_run_digest
from database import (
    begin_scrape_run,
    finish_scrape_run,
    initialize_database,
    sync_performer_events,
)
from scrapers import SCRAPERS


ROOT = Path(__file__).parent
PERFORMERS_FILE = ROOT / "data" / "performers.csv"
OUTPUT_FILE = ROOT / "output" / "events.csv"


def load_performers() -> list[dict[str, str]]:
    with PERFORMERS_FILE.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main() -> None:
    initialize_database()
    run_id = begin_scrape_run()
    all_events = []
    total_new = 0
    total_removed = 0

    for performer in load_performers():
        if performer["active"].lower() != "true":
            continue

        if performer["scraper"] not in SCRAPERS:
            print(
                f"Skipping {performer['performer']}: "
                f"unsupported scraper {performer['scraper']}"
            )
            continue

        try:
            scraper_name = performer["scraper"]

            scraper_class = SCRAPERS.get(scraper_name)

            if scraper_class is None:
                raise ValueError(
                    f"Unknown scraper '{scraper_name}'."
                )

            scraper = scraper_class(
                performer["tour_page_url"],
                performer=performer["performer"],
            )
            events = [
                event
                for event in scraper.scrape()
                if is_upcoming(event.date)
            ]
        except Exception as exc:
            print(f"FAILED: {performer['performer']}: {exc}")
            continue

        result = sync_performer_events(performer["performer"], events)
        print(
            f"{performer['performer']}: {result.new} new, "
            f"{result.existing} existing, {result.removed} removed"
        )
        total_new += result.new
        total_removed += result.removed
        all_events.extend(events)

    all_events.sort(key=lambda event: event.date or "9999-12-31")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)

    fieldnames = list(asdict(all_events[0]).keys()) if all_events else []

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if all_events:
            writer.writeheader()
            writer.writerows(asdict(event) for event in all_events)

    print(f"\nSaved {len(all_events)} active upcoming events to {OUTPUT_FILE}")
    summary = finish_scrape_run(run_id, total_new, total_removed)
    print(format_run_digest(summary))

# Check if an event is upcoming based on its date

def is_upcoming(date_text: str | None) -> bool:
    if not date_text:
        return False

    normalized = date_text.replace("Z", "+00:00")

    try:
        event_date = datetime.fromisoformat(normalized)
    except ValueError:
        return False

    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)

    return event_date >= datetime.now(timezone.utc)


if __name__ == "__main__":
    main()
