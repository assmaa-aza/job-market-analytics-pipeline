# Job Market Analytics: Morocco Tech Jobs

End-to-end ELT pipeline collecting job offers from Rekrute.com,
modeled in Snowflake with dbt, orchestrated by Airflow, visualized in Power BI.

> Status: 🚧 in progress. Stage 1 (ingestion) done.

## Context
Rebuilt independently as a learning project, inspired by a team project
I took part in (design and stack). All code in this repo is my own.

## Architecture (target)
Rekrute → Python scraper → raw JSON → Snowflake (Bronze) → dbt (Silver, Gold) → Power BI
                         orchestrated by Airflow

## Stage 1: Ingestion ✅
- `scrape_offer(url)`: extracts one offer from the JSON-LD block (stable,
  structured) plus the HTML info rows; fails loudly if required fields are missing.
- `get_offer_urls()`: paginated discovery of offer URLs.
- `scrape_batch()`: tolerant at batch level, fails only if failure rate > 20%.
- `content_hash`: fingerprint of an offer's content for change detection.

## Design decisions
- JSON-LD over visual HTML selectors: stable across redesigns, absolute dates.
- Schema drift handled with a label mapping (`Secteur`/`Secteurs` → `secteur`).
- Strict at unit level, monitored at batch level.

## Run it
pip install -r requirements.txt
python src/scraper.py

## Roadmap
- [x] Stage 1: scraping
- [ ] Stage 2: Snowflake Bronze (VARIANT)
- [ ] Stage 3: dbt Silver/Gold + tests
- [ ] Stage 4: Airflow orchestration
- [ ] Stage 5: dashboard
- [ ] Stage 6: hardening (secrets, idempotent loads)

## Responsible scraping
Delay between requests, no personal data collected, site terms respected.