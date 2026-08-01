from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from scrapers.komi import KomiScraper


ROOT = Path(__file__).parent
PERFORMERS_FILE = ROOT / "data" / "performers.csv"
OUTPUT_FILE = ROOT / "output" / "events.csv"


def load_performers() -> list[dict[str, str]]:
    with PERFORMERS_FILE.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main() -> None:
    all_events = []

    for performer in load_performers():
        if performer["active"].lower() != "true":
            continue

        if performer["scraper"] != "komi":
            print(
                f"Skipping {performer['performer']}: "
                f"unsupported scraper {performer['scraper']}"
            )
            continue

        try:
            scraper = KomiScraper(performer["tour_page_url"])
            events = scraper.scrape()
        except Exception as exc:
            print(f"FAILED: {performer['performer']}: {exc}")
            continue

        print(f"{performer['performer']}: {len(events)} events")
        all_events.extend(events)

    OUTPUT_FILE.parent.mkdir(exist_ok=True)

    fieldnames = list(asdict(all_events[0]).keys()) if all_events else []

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if all_events:
            writer.writeheader()
            writer.writerows(asdict(event) for event in all_events)

    print(f"\nSaved {len(all_events)} events to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()