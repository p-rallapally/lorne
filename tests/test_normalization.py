from normalization import linktree_location, linktree_venue
from scrapers.linktree import LinktreeScraper


def test_extracts_venue_from_month_first_linktree_label() -> None:
    assert linktree_venue(
        "SEPTEMBER 10 - GILFORD, NH - BankNH Pavilion"
    ) == "BankNH Pavilion"


def test_extracts_venue_after_show_time() -> None:
    assert linktree_venue(
        "SEPTEMBER 11 - MISSISSAUGA, CA - 7:30PM - Great Outdoors Comedy Festival"
    ) == "Great Outdoors Comedy Festival"


def test_returns_none_when_label_has_no_venue() -> None:
    assert linktree_venue("BROOKLYN - SEPTEMBER 11TH") is None
    assert linktree_venue("FORT COLLINS, C.O. - AUGUST 20TH - 22ND") is None


def test_date_range_is_not_mistaken_for_location() -> None:
    assert LinktreeScraper._extract_location(
        "FORT COLLINS, C.O. - AUGUST 20TH - 22ND"
    ) == "Fort Collins, CO"


def test_extracts_location_around_show_time() -> None:
    assert linktree_location(
        "AUGUST 21 - 7:00PM SHOW - PITTSBURGH, PA - Bottlerocket Social Hall"
    ) == "Pittsburgh, PA"
