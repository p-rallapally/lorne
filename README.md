# Scraper Night Live

> A data pipeline for tracking live performances by current and former Saturday Night Live cast members.

## Why?

Every performer has their own touring website, and keeping up with 17 different Instagram accounts and signing up for 17 different mailing lists when 95% of their events aren't in my area seems redundant. 

The aim of this project is to efficiently standardize and aggregate event dates, highlighting the ones that are in a given location.

## How it works

The pipeline consists of three stages:

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

Each scraper is responsible for extracting event information from a specific website platform and converting it into a common `Event` model.

The runner reads a configuration file of performers, invokes the appropriate scraper, and aggregates all discovered events into a single output.

## Current support

| Platform | Status | Notes |
|----------|--------|-------|
| Komi | ✅ | Supports native Komi events |
| Komi + Bandsintown | ✅ | Automatically detects embedded Bandsintown feeds |
| Linktree | 🚧 | Planned |
| Punchup | 🚧 | Planned |
| Personal websites | 🚧 | Planned |

## Event schema

Every scraper outputs the same structure:

```python
Event(
    performer,
    event_id,
    date,
    venue,
    location,
    ticket_url,
    sold_out,
    source_url,
    source_platform,
    scraped_at,
)
```

Regardless of where the event originated, downstream code never needs to know the underlying platform.

## Running

Clone the repository

```bash
git clone https://github.com/p-rallapally/scraper-night-live.git
cd scraper-night-live
```

Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run the pipeline

```bash
python run.py
```

Results are written to

```
output/events.csv
```

and stored in

```
data/events.db
```

## Project goals

- Aggregate performances from all current SNL cast members
- Support the most common event-hosting platforms
- Provide a unified event dataset independent of source
- Eventually power a searchable interface for finding performances near a user's location