# Stage 1 Report: Data Ingestion (Rekrute.com Scraper)

**Project:** Job Market Analytics, Morocco tech jobs
**Stage:** 1 of 6, ingestion
**Status:** Completed
**Author:** Assmaa Azaroual

---

## 1. Objective

Build a reliable, reproducible process that collects job offers from Rekrute.com and produces clean, validated, structured records, ready to be loaded into the Bronze layer of a data warehouse in Stage 2.

The goals of this stage were:

1. Understand how the source site exposes its data.
2. Extract each offer into one consistent record.
3. Detect and fail on bad data instead of silently passing it on.
4. Collect offers across several listing pages.
5. Document the choices so that every decision can be justified.

## 2. Context

This project is an independent rebuild of a team project in which I took part during my engineering studies (same use case and technology stack). During the team project my contribution was theoretical, so I decided to rebuild the pipeline myself, stage by stage, and to fix the weaknesses I identified in the original design (see section 8). All code in this repository was written for this rebuild.

## 3. Source Analysis

I inspected an offer page with the browser developer tools (F12) and found that the data is available in two places:

| Source | What it contains | Pros | Cons |
|---|---|---|---|
| **JSON-LD block** (`<script type="application/ld+json">`, type `JobPosting`) | Title, company, date posted, deadline, contract type, city, description | Structured, stable across redesigns, absolute dates | Does not contain every field |
| **HTML info rows** (`div.jo-infoRow`) | Study level, training field, function, sector, experience, remote work | Contains the fields missing from JSON-LD | Depends on CSS classes, which can change with a redesign |

**Decision:** use a hybrid approach. JSON-LD is the primary source, and the HTML rows complete it.

A key observation concerns dates. The visible page only shows a *relative* date ("Publiée aujourd'hui"), which becomes wrong as soon as it is stored and read later. The JSON-LD field `datePosted` is an *absolute* timestamp, so it remains correct forever and is the only date used for analysis.

## 4. Output Data Model

Each offer is one record (dictionary) with the following fields.

| Field | Source | Notes |
|---|---|---|
| `url` | URL | Offer identifier, tracking parameters removed |
| `titre` | JSON-LD | Required |
| `entreprise` | JSON-LD | Required |
| `date_publication` | JSON-LD `datePosted` | Required, absolute timestamp |
| `date_limite` | JSON-LD `validThrough` | |
| `ville` | JSON-LD | City, not yet normalized |
| `description` | JSON-LD | HTML entities decoded |
| `formation` | HTML | Optional, absent in some offers |
| `niveau_etude` | HTML | |
| `fonction` | HTML | |
| `secteur` | HTML | Merges two source labels (section 6) |
| `experience` | HTML | Raw text, parsed later in Silver |
| `contrat` | HTML | |
| `teletravail` | HTML | |
| `scraped_at` | generated | UTC collection timestamp |
| `content_hash` | generated | SHA-256 fingerprint of the content, excluding `scraped_at` |

Unknown HTML labels are kept with an `autre_` prefix, so a new field added by the site is never silently lost.

## 5. Implementation

The code is in `src/scraper.py`, organized into functions that each do one job.

| Function | Responsibility |
|---|---|
| `scrape_offer(url)` | One URL becomes one clean record. Strict: raises an error if a required field is missing or the JSON-LD block is absent. |
| `get_offer_urls(max_pages)` | Walks the listing pages (`?p=N`), collects offer URLs, removes duplicates, and stops as soon as a page brings no new URL. |
| `scrape_batch(urls)` | Loops over URLs, catches individual failures, logs them, and fails the whole task only if the failure rate exceeds 20%. |

Output is written to `data/offers.json` (excluded from version control). The output path is computed from the script's own location, so the code runs unchanged on any machine.

## 6. Data Quality Findings

A first run on 10 offers, profiled with pandas, revealed three issues that shaped the design.

**6.1 Schema drift.** The same information appeared under two labels, `Secteur` (1 missing out of 10) and `Secteurs` (9 missing out of 10). Each offer carried exactly one of them. Loading this as-is would have produced two half-empty columns. *Fix:* a `LABEL_MAP` dictionary maps all known label variants to one clean column name.

**6.2 Legitimately optional fields.** `formation` was missing in 3 of 10 offers because those offers do not specify it. This is not an error, so it is not in the list of required fields.

**6.3 Sampling bias.** All 10 offers in the first sample were `CDI`, which does not reflect the real distribution of contract types. The cause was scraping only the first listing page of one sort order. *Fix:* pagination (3 pages, 30 unique URLs in the test run).

Other values will need cleaning in the Silver layer (Stage 3): experience ranges such as `Intermédiaire (3 à 5 ans)` must be parsed into numeric minimum and maximum, and cities must be normalized and mapped to regions.

## 7. Results of the Collection Run

| Metric | Value |
|---|---|
| Listing pages scraped | 3 |
| Unique offer URLs found | 30 |
| Offers successfully scraped | [TO FILL] |
| Offers failed | [TO FILL] |
| Failure rate | [TO FILL] |
| Contract types observed | [TO FILL: paste `value_counts()`] |

## 8. Design Decisions and Trade-offs

| Decision | Reason | Trade-off |
|---|---|---|
| JSON-LD first, HTML second | Stability and absolute dates | Two extraction paths to maintain |
| Strict at record level, tolerant at batch level | One malformed offer should not lose the other 299, yet a systemic problem must stop the pipeline and alert someone | Needs a tuned failure threshold |
| Fail loudly on missing required fields | A pipeline running unattended must produce a visible error, which also lets an orchestrator retry or stop, instead of loading empty rows | Stricter than returning `None` |
| `content_hash` on each record | Enables change detection without comparing full texts | Hash is only as good as the fields included |
| 2-second delay between requests | Avoid overloading the source server | Slower collection |
| URLs stripped of tracking parameters | The same offer must never appear under two URLs | None significant |

### Load strategy (decision for Stage 2)

In the original team project, the loader inserted every scraped offer on every run, so the Bronze table accumulated one duplicate row per offer per day, and the Silver layer removed them with `ROW_NUMBER() OVER (PARTITION BY url ORDER BY scraped_at DESC)`. This works but makes the load non-idempotent (re-running it changes the result) and wastes storage.

Planned approach for this rebuild: insert into Bronze only when the pair `(url, content_hash)` is not already present. This gives an idempotent load, no daily duplicates, and a real history, because a modified offer creates a new version. Silver can still select the latest version per URL. This choice depends on the analysis goal: analyzing trends over time and offer lifetimes requires history, whereas a plain upsert on URL would erase it.

## 9. Limitations

- The scraper depends on the site's current structure. A redesign could break the HTML extraction, although JSON-LD makes the core fields more resilient.
- Only a limited number of listing pages is scraped. Full coverage requires larger runs and measured delays.
- No salary data is collected, because it is not exposed consistently.
- The listing-page URL parameters (`s`, `o`) are kept as observed, and their exact meaning is not yet documented.
- Collection respects reasonable request pacing, but the site's terms of use should be rechecked before any large-scale scraping.

## 10. Reproducibility

```bash
pip install -r requirements.txt
python src/scraper.py          # run from the project root
```

Output: `data/offers.json`.

## 11. Next Stage

**Stage 2: Bronze layer.** Learn SQL fundamentals, then load the JSON records into a raw table with a `VARIANT` column in Snowflake, implementing the `(url, content_hash)` load strategy and querying the semi-structured data with SQL.