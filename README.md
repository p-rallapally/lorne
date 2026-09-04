# Lorne

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
- Standardized event schema across sources
- Stateful SQLite storage with event upserts
- Detection of new, existing, and removed events
- CSV export of active upcoming events
- Geocoding of event locations
- Location and radius-based event search
- Automated daily scraping with GitHub Actions

## Searching

Search for upcoming events near a location:

```bash
python search.py --near "Santa Barbara, CA"

```

Specify a radius and/or performer: 

```bash
python search.py --near "San Francisco, CA" --radius 100 --performer "Michael Longfellow" 

```

## Running

```bash
git clone https://github.com/p-rallapally/scraper-night-live.git
cd scraper-night-live

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Create and install the virtual environment once. On later terminal sessions,
reuse it with only:

```bash
source .venv/bin/activate
```

Create a `.env` file:

```text
PUNCHUP_SUPABASE_KEY=...
```

Run the pipeline:

```bash
python run.py
```

Run the website locally:

```bash
flask --app app run
```

In production (including Render), use:

```bash
gunicorn app:app
```

Show the concise summary from the latest pipeline run:

```bash
python changes.py
```

## GitHub Actions automation

The `Scrape events` workflow runs daily at 15:17 UTC and can also be run
manually from the repository's **Actions** tab. It commits `data/events.db`
and `output/events.csv` so event history persists between hosted runners.

Before the first run, add `PUNCHUP_SUPABASE_KEY` under **Settings → Secrets
and variables → Actions**, then commit the current database and CSV once.

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
- Improve automated change reporting/notifications
- Interactive map of upcoming performances
- Web interface for location-based discovery
- Tests and CI
