from __future__ import annotations
from email import parser
from math import asin, cos, radians, sin, sqrt
from geopy.geocoders import Nominatim
import argparse
import sqlite3
from datetime import date
from pathlib import Path


ROOT = Path(__file__).parent
DATABASE_FILE = ROOT / "data" / "events.db"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search upcoming SNL cast-member performances."
    )

    parser.add_argument(
        "--performer",
        help="Filter by performer name, such as 'Sarah Sherman'.",
    )

    parser.add_argument(
        "--location",
        help="Filter by city, state, country, or other location text.",
    )

    parser.add_argument(
        "--after",
        help="Only show events on or after this date, in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--before",
        help="Only show events on or before this date, in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Include past and inactive events.",
    )

    parser.add_argument(
    "--near",
    help="Search near a city or address, such as 'Santa Barbara, CA'.",
)

    parser.add_argument(
        "--radius",
        type=float,
        default=100,
        help="Search radius in miles. Defaults to 100.",
    )

    return parser.parse_args()


def validate_date(value: str | None, argument_name: str) -> str | None:
    if value is None:
        return None

    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"{argument_name} must use YYYY-MM-DD format."
        ) from exc


def distance_miles(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius_miles = 3958.8

    latitude_difference = radians(lat2 - lat1)
    longitude_difference = radians(lon2 - lon1)

    a = (
        sin(latitude_difference / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(longitude_difference / 2) ** 2
    )

    return 2 * earth_radius_miles * asin(sqrt(a))

def search_events(
    performer: str | None = None,
    location: str | None = None,
    after: str | None = None,
    before: str | None = None,
    include_all: bool = False,
    near: str | None = None,
    radius: float = 100,
) -> list[sqlite3.Row] | list[tuple[sqlite3.Row, float]]:
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_FILE}. Run python run.py first."
        )

    conditions: list[str] = []
    parameters: list[str] = []

    if performer:
        conditions.append("LOWER(performer) LIKE LOWER(?)")
        parameters.append(f"%{performer}%")

    if location:
        conditions.append("LOWER(location) LIKE LOWER(?)")
        parameters.append(f"%{location}%")

    if after:
        conditions.append("DATE(date) >= DATE(?)")
        parameters.append(after)

    if before:
        conditions.append("DATE(date) <= DATE(?)")
        parameters.append(before)

    if not include_all:
        conditions.append("DATE(date) >= DATE('now')")
        conditions.append("active = 1")

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            performer,
            event_id,
            date,
            end_date,
            venue,
            location,
            ticket_url,
            sold_out,
            source_url,
            source_platform,
            latitude,
            longitude
        FROM events
        {where_clause}
        ORDER BY DATE(date), performer, venue
    """

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(query, parameters).fetchall()
    finally:
        connection.close()

    if not near:
        return rows

    search_latitude, search_longitude = geocode_search_location(near)

    matching_rows: list[tuple[sqlite3.Row, float]] = []

    for row in rows:
        latitude = row["latitude"]
        longitude = row["longitude"]

        if latitude is None or longitude is None:
            continue

        distance = distance_miles(
            search_latitude,
            search_longitude,
            latitude,
            longitude,
        )

        if distance <= radius:
            matching_rows.append((row, distance))

    matching_rows.sort(
        key=lambda item: (
            item[0]["date"] or "9999-12-31",
            item[1],
        )
    )

    return matching_rows

def geocode_search_location(query: str) -> tuple[float, float]:
    geolocator = Nominatim(
        user_agent=(
            "scraper-night-live/0.3 "
            "(github.com/p-rallapally/scraper-night-live)"
        )
    )

    result = geolocator.geocode(
        query,
        exactly_one=True,
        country_codes="us,ca",
    )

    if result is None:
        raise ValueError(f"Could not find location: {query}")

    return result.latitude, result.longitude


def format_date(value: str | None) -> str:
    if not value:
        return "Unknown date"

    try:
        return date.fromisoformat(value[:10]).strftime("%b %d, %Y")
    except ValueError:
        return value


def print_events(events: list[sqlite3.Row] | list[tuple[sqlite3.Row, float]]) -> None:
    if not events:
        print("No matching events found.")
        return

    print(f"Found {len(events)} event{'s' if len(events) != 1 else ''}.\n")

    current_performer: str | None = None

    for event in events:
        if isinstance(event, tuple):
            row, distance = event
        else:
            row = event
            distance = None

        performer = row["performer"]

        if performer != current_performer:
            if current_performer is not None:
                print()

            print(performer)
            print("-" * len(performer))
            current_performer = performer

        start_date = format_date(row["date"])
        end_date = row["end_date"]

        if end_date:
            date_text = f"{start_date}–{format_date(end_date)}"
        else:
            date_text = start_date

        venue = row["venue"] or "Unknown venue"
        location = row["location"] or "Unknown location"
        ticket_url = row["ticket_url"] or row["source_url"]

        if distance is not None:
            location = f"{location} ({distance:.1f} miles away)"

        print(f"{date_text} — {venue}")
        print(f"  {location}")
        print(f"  {ticket_url}")


def main() -> None:
    args = parse_arguments()

    try:
        after = validate_date(args.after, "--after")
        before = validate_date(args.before, "--before")

        events = search_events(
            performer=args.performer,
            location=args.location,
            after=after,
            before=before,
            include_all=args.all,
            near=args.near,
            radius=args.radius,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print_events(events)


if __name__ == "__main__":
    main()