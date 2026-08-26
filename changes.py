from __future__ import annotations

import sqlite3

from database import initialize_database, latest_scrape_run


def format_run_digest(run: sqlite3.Row) -> str:
    status = "finished" if run["finished_at"] else "in progress"
    active = run["total_active"]
    active_text = str(active) if active is not None else "unknown"
    return (
        f"Scrape run #{run['run_id']} {status}: "
        f"{run['total_new']} new, {run['total_removed']} removed, "
        f"{active_text} active"
    )


def latest_digest() -> str:
    initialize_database()
    run = latest_scrape_run()
    if run is None:
        return "No scrape runs recorded."
    return format_run_digest(run)


def main() -> None:
    print(latest_digest())


if __name__ == "__main__":
    main()
