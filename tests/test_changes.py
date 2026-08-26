from changes import format_run_digest


def test_format_run_digest() -> None:
    run = {
        "run_id": 12,
        "finished_at": "2026-01-01T00:01:00+00:00",
        "total_new": 2,
        "total_removed": 1,
        "total_active": 42,
    }
    assert format_run_digest(run) == (
        "Scrape run #12 finished: 2 new, 1 removed, 42 active"
    )
