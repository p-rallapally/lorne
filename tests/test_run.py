from __future__ import annotations

import run


class SuccessfulEmptyScraper:
    def __init__(self, url, performer=None):
        pass

    def scrape(self):
        return []


class FailedScraper:
    def __init__(self, url, performer=None):
        pass

    def scrape(self):
        raise RuntimeError("deliberate failure")


def test_failed_scrape_is_not_synced(tmp_path, monkeypatch) -> None:
    performers = [
        {
            "performer": "Successful Performer",
            "active": "true",
            "scraper": "success",
            "tour_page_url": "https://example.com/success",
        },
        {
            "performer": "Failed Performer",
            "active": "true",
            "scraper": "failure",
            "tour_page_url": "https://example.com/failure",
        },
    ]
    synced = []
    monkeypatch.setattr(run, "load_performers", lambda: performers)
    monkeypatch.setattr(
        run,
        "SCRAPERS",
        {"success": SuccessfulEmptyScraper, "failure": FailedScraper},
    )
    monkeypatch.setattr(run, "initialize_database", lambda: None)
    monkeypatch.setattr(run, "begin_scrape_run", lambda: 7)
    finished = []
    monkeypatch.setattr(
        run,
        "finish_scrape_run",
        lambda run_id, new, removed: finished.append((run_id, new, removed))
        or {
            "run_id": run_id,
            "finished_at": "now",
            "total_new": new,
            "total_removed": removed,
            "total_active": 0,
        },
    )
    monkeypatch.setattr(
        run,
        "sync_performer_events",
        lambda performer, events: synced.append((performer, events))
        or type("Result", (), {"new": 0, "existing": 0, "removed": 1})(),
    )
    monkeypatch.setattr(run, "OUTPUT_FILE", tmp_path / "events.csv")

    run.main()

    assert synced == [("Successful Performer", [])]
    assert finished == [(7, 0, 1)]
