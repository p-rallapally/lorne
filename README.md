# Scraper Night Live

> A data pipeline for tracking live performances by current and former Saturday Night Live cast members.

## Why?

Every performer has their own touring website. Keeping up with 17 different Instagram accounts and mailing lists when 95% of their shows aren't near me seemed redundant.

This project standardizes and aggregates tour dates across platforms, making it easy to find performances by location.

## How it works

```
Performer URLs
        │
        ▼
 Platform-specific scrapers
        │
        ▼
 Standardized Event objects
        │
        ├── SQLite database
        └── CSV export
```

Each scraper extracts events from a specific platform and converts them into a common `Event` model. The runner reads a performer configuration file, invokes the appropriate scraper, and aggregates all discovered events into a single dataset.

## Current support

| Platform | Status |
|----------|--------|
| Komi | ✅ |
| Komi + Bandsintown | ✅ |
| Linktree | ✅ |
| Punchup | ✅ |
| Personal websites | 🚧 |

## Event schema

Every scraper outputs the same structure:

```python
Event(
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
    scraped_at,
)
```

Downstream code never needs to know where an event came from.

## Features

- Multi-platform event aggregation
- SQLite database + CSV export
- Automatic event normalization
- Geocoding for venue locations
- Radius-based event search

## Running

```bash
git clone https://github.com/p-rallapally/scraper-night-live.git
cd scraper-night-live

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file:

```text
PUNCHUP_SUPABASE_KEY=...
```

Run the pipeline:

```bash
python run.py
```

Events are written to:

```
output/events.csv
```

and stored in:

```
data/events.db
```

## Roadmap

- Support additional event-hosting platforms
- Detect newly added, removed, and updated events
- Interactive map of upcoming performances
- CLI and web interface for location-based search