from scrapers.komi import KomiScraper


def test_sarah_native_komi_events() -> None:
    events = KomiScraper(
        "https://sarahsquirm.komi.io/"
    ).scrape()

    assert len(events) > 0
    assert all(event.performer == "Sarah Squirm" for event in events)
    assert any(event.source_platform == "komi" for event in events)


def test_michael_bandsintown_events() -> None:
    events = KomiScraper(
        "https://michaellongfellow.komi.io/"
    ).scrape()

    assert len(events) > 0
    assert all(event.performer == "Michael Longfellow" for event in events)
    assert any(
        event.source_platform == "bandsintown"
        for event in events
    )
    assert any(event.ticket_url for event in events)