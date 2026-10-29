import json, html, re, time, hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.rekrute.com/offres.html"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"   # project_root/data
OUTPUT_FILE = DATA_DIR / "offers.json"
REQUIRED = ["titre", "date_publication", "entreprise", "url"]

LABEL_MAP = {
    "Formation": "formation",
    "Niveau d'étude": "niveau_etude",
    "Fonction": "fonction",
    "Secteur": "secteur",
    "Secteurs": "secteur",      # both variants -> same column
    "Expérience": "experience",
    "Contrat": "contrat",
    "Télétravail": "teletravail",
}


def scrape_offer(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ld = None
    for tag in soup.find_all("script", type="application/ld+json"):
        data = json.loads(tag.string, strict=False)
        if data.get("@type") == "JobPosting":
            ld = data
            break
    if ld is None:
        raise ValueError(f"No JobPosting JSON-LD found: {url}")

    offre = {
        "url": url,
        "titre": ld.get("title"),
        "entreprise": ld.get("hiringOrganization", {}).get("name"),
        "date_publication": ld.get("datePosted"),
        "date_limite": ld.get("validThrough"),
        "ville": ld.get("jobLocation", {}).get("address", {}).get("addressLocality"),
        "description": html.unescape(ld.get("description", "")).strip(),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    for row in soup.select("div.jo-infoRow"):
        label = row.select_one(".jo-infoLabel").get_text(strip=True)
        value = row.select_one(".jo-infoValue").get_text(strip=True)
        offre[LABEL_MAP.get(label, f"autre_{label}")] = value

    # fingerprint of the content (ignores scraped_at, which always changes)
    contenu = json.dumps(
        {k: v for k, v in offre.items() if k != "scraped_at"},
        sort_keys=True, ensure_ascii=False,
    )
    offre["content_hash"] = hashlib.sha256(contenu.encode("utf-8")).hexdigest()

    missing = [f for f in REQUIRED if not offre.get(f)]
    if missing:
        raise ValueError(f"Missing {missing} for {url}")
    return offre


def get_offer_urls(max_pages=3, delay=2):
    urls = set()
    for page in range(1, max_pages + 1):
        resp = requests.get(BASE, params={"p": page, "s": 1, "o": 1},
                            headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        found = {urljoin(BASE, a["href"]).split("?")[0]
                 for a in soup.find_all("a", href=True)
                 if re.search(r"offre-emploi-.*\.html", a["href"])}
        new = found - urls
        print(f"page {page}: {len(found)} URLs, {len(new)} new")
        if not new:
            break
        urls |= new
        time.sleep(delay)
    return sorted(urls)


def scrape_batch(urls, max_failure_rate=0.2, delay=2):
    offers, failures = [], []
    for url in urls:
        try:
            offers.append(scrape_offer(url))
        except Exception as e:
            failures.append((url, str(e)))
            print(f"FAILED {url}: {e}")
        time.sleep(delay)
    rate = len(failures) / max(len(urls), 1)
    print(f"{len(offers)} ok, {len(failures)} failed ({rate:.0%})")
    if rate > max_failure_rate:
        raise RuntimeError(f"Failure rate {rate:.0%} above threshold")
    return offers


if __name__ == "__main__":
    urls = get_offer_urls(max_pages=3)
    print(len(urls), "unique URLs")
    offers = scrape_batch(urls)

    DATA_DIR.mkdir(exist_ok=True)            # create data/ if it doesn't exist
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(offers)} offers to {OUTPUT_FILE}")