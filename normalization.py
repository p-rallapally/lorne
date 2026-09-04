from __future__ import annotations

import re


MONTH_NAME = (
    r"JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|"
    r"JUN(?:E)?|JUL(?:Y)?|AUG(?:UST)?|SEP(?:T(?:EMBER)?)?|"
    r"OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?"
)


def linktree_venue(label: str | None) -> str | None:
    """Extract a venue from a Linktree event label when one is present."""
    if not label:
        return None

    parts = [part.strip() for part in re.split(r"\s+[-–—]\s+", label)]
    date_index = next(
        (
            index
            for index, part in enumerate(parts)
            if re.search(rf"\b(?:{MONTH_NAME})\b", part, re.IGNORECASE)
        ),
        None,
    )
    if date_index is None:
        return label.strip() or None

    # Month-first labels put the location immediately after the date. Labels
    # that start with a location put candidate venue text after the date.
    candidates = parts[2:] if date_index == 0 else parts[date_index + 1 :]
    for candidate in reversed(candidates):
        if re.fullmatch(r"\d{1,2}(?:ST|ND|RD|TH)?", candidate, re.IGNORECASE):
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}\s*(?:AM|PM)(?:\s+SHOW)?", candidate, re.IGNORECASE):
            continue
        if re.fullmatch(r"\(?(?:EARLY|LATE)\s+SHOW\)?", candidate, re.IGNORECASE):
            continue
        return candidate.strip() or None
    return None


def linktree_location(label: str | None) -> str | None:
    """Extract and normalize a location from a Linktree event label."""
    if not label:
        return None
    parts = [part.strip() for part in re.split(r"\s+[-–—]\s+", label)]
    date_index = next(
        (
            index for index, part in enumerate(parts)
            if re.search(rf"\b(?:{MONTH_NAME})\b", part, re.IGNORECASE)
        ),
        None,
    )
    if date_index is None:
        return None

    if date_index > 0:
        location = re.sub(
            r"^\**NETFLIX TAPING\**\s*", "", parts[0], flags=re.IGNORECASE
        )
    else:
        candidates = parts[1:]
        venue = linktree_venue(label)
        if venue and candidates and candidates[-1] == venue:
            candidates.pop()
        candidates = [
            item for item in candidates
            if not re.fullmatch(
                r"\d{1,2}:\d{2}\s*(?:AM|PM)(?:\s+SHOW)?",
                item,
                re.IGNORECASE,
            )
        ]
        location = candidates[0] if candidates else ""

    location = re.sub(r"\b([A-Z])\.([A-Z])\.", r"\1\2", location.upper())
    match = re.fullmatch(r"(.+?),?\s+([A-Z]{2})", location)
    if match:
        return f"{match.group(1).strip(' ,').title()}, {match.group(2)}"
    return location.title() or None
