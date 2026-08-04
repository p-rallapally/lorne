from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from geopy.location import Location


ROOT = Path(__file__).parent
DATABASE_FILE = ROOT / "data" / "events.db"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Geocode event venues and locations."
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of unique locations to geocode.",
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry locations that previously failed to geocode.",
    )

    return parser.parse_args()


def connect() -> sqlite3.Connection:
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_FILE}. "
            "Run python run.py first."
        )

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def column_exists(
    connection: sqlite3.Connection,
    table: str,
    column: str,
) -> bool:
    rows = connection.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return any(row["name"] == column for row in rows)


def initialize_geocoding_schema() -> None:
    """
    Add coordinate columns to events and create a reusable location cache.
    """

    with connect() as connection:
        if not column_exists(connection, "events", "latitude"):
            connection.execute(
                "ALTER TABLE events ADD COLUMN latitude REAL"
            )

        if not column_exists(connection, "events", "longitude"):
            connection.execute(
                "ALTER TABLE events ADD COLUMN longitude REAL"
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                query TEXT PRIMARY KEY,
                latitude REAL,
                longitude REAL,
                matched_address TEXT,
                status TEXT NOT NULL,
                attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def build_geocoding_query(
    venue: str | None,
    location: str | None,
) -> str | None:
    clean_venue = venue.strip() if venue else ""
    clean_location = location.strip().rstrip(",") if location else ""

    # Linktree venue fields currently contain the entire listing label,
    # so use the parsed location alone for those records.
    if clean_location:
        return clean_location

    if clean_venue:
        return clean_venue

    return None


def load_pending_queries(
    connection: sqlite3.Connection,
    retry_failed: bool,
    limit: int | None,
) -> list[str]:
    """
    Return unique event-location queries not already successfully cached.
    """

    rows = connection.execute(
        """
        SELECT DISTINCT venue, location
        FROM events
        WHERE active = 1
          AND latitude IS NULL
          AND longitude IS NULL
          AND (venue IS NOT NULL OR location IS NOT NULL)
        """
    ).fetchall()

    queries: list[str] = []

    for row in rows:
        query = build_geocoding_query(
            venue=row["venue"],
            location=row["location"],
        )

        if not query:
            continue

        cached = connection.execute(
            """
            SELECT status
            FROM geocoding_cache
            WHERE query = ?
            """,
            (query,),
        ).fetchone()

        if cached:
            if cached["status"] == "success":
                continue

            if cached["status"] == "failed" and not retry_failed:
                continue

        queries.append(query)

    queries = sorted(set(queries))

    if limit is not None:
        queries = queries[:limit]

    return queries


def save_geocoding_result(
    connection: sqlite3.Connection,
    query: str,
    location: Location | None,
) -> None:
    if location is None:
        connection.execute(
            """
            INSERT INTO geocoding_cache (
                query,
                latitude,
                longitude,
                matched_address,
                status,
                attempted_at
            )
            VALUES (?, NULL, NULL, NULL, 'failed', CURRENT_TIMESTAMP)
            ON CONFLICT(query)
            DO UPDATE SET
                latitude = NULL,
                longitude = NULL,
                matched_address = NULL,
                status = 'failed',
                attempted_at = CURRENT_TIMESTAMP
            """,
            (query,),
        )
        return

    connection.execute(
        """
        INSERT INTO geocoding_cache (
            query,
            latitude,
            longitude,
            matched_address,
            status,
            attempted_at
        )
        VALUES (?, ?, ?, ?, 'success', CURRENT_TIMESTAMP)
        ON CONFLICT(query)
        DO UPDATE SET
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            matched_address = excluded.matched_address,
            status = 'success',
            attempted_at = CURRENT_TIMESTAMP
        """,
        (
            query,
            location.latitude,
            location.longitude,
            location.address,
        ),
    )


def apply_cached_coordinates(
    connection: sqlite3.Connection,
) -> int:
    """
    Apply successful cached coordinates to matching events.
    """

    rows = connection.execute(
        """
        SELECT
            performer,
            event_id,
            source_platform,
            venue,
            location
        FROM events
        WHERE latitude IS NULL
           OR longitude IS NULL
        """
    ).fetchall()

    updated = 0

    for row in rows:
        query = build_geocoding_query(
            venue=row["venue"],
            location=row["location"],
        )

        if not query:
            continue

        cached = connection.execute(
            """
            SELECT latitude, longitude
            FROM geocoding_cache
            WHERE query = ?
              AND status = 'success'
            """,
            (query,),
        ).fetchone()

        if not cached:
            continue

        connection.execute(
            """
            UPDATE events
            SET latitude = ?,
                longitude = ?
            WHERE source_platform = ?
              AND event_id = ?
            """,
            (
                cached["latitude"],
                cached["longitude"],
                row["source_platform"],
                row["event_id"],
            ),
        )

        updated += 1

    return updated


def main() -> None:
    args = parse_arguments()

    try:
        initialize_geocoding_schema()

        geolocator = Nominatim(
            user_agent="scraper-night-live/0.3 "
            "(github.com/p-rallapally/scraper-night-live)"
        )

        geocode = RateLimiter(
            geolocator.geocode,
            min_delay_seconds=1.1,
            max_retries=2,
            error_wait_seconds=5,
            swallow_exceptions=True,
        )

        with connect() as connection:
            pending_queries = load_pending_queries(
                connection=connection,
                retry_failed=args.retry_failed,
                limit=args.limit,
            )

            print(
                f"Found {len(pending_queries)} "
                "unique locations to geocode.\n"
            )

            for index, query in enumerate(pending_queries, start=1):
                print(
                    f"[{index}/{len(pending_queries)}] "
                    f"Geocoding: {query}"
                )

                result = geocode(
                    query,
                    exactly_one=True,
                    addressdetails=False,
                    country_codes="us,ca",
                )

                save_geocoding_result(
                    connection=connection,
                    query=query,
                    location=result,
                )

                if result is None:
                    print("  No match")
                else:
                    print(
                        f"  {result.latitude:.6f}, "
                        f"{result.longitude:.6f}"
                    )
                    print(f"  Matched: {result.address}")

                connection.commit()

            updated = apply_cached_coordinates(connection)
            connection.commit()

        print(f"\nUpdated coordinates for {updated} events.")

    except FileNotFoundError as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()