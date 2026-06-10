"""
Milestone 3 — Document Ingestion
Fetches raw text from each off-campus housing source and saves it as a JSON
file in documents/ with a consistent schema for the chunking step.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCES = [
    {
        "id": "01_the_standard_at_tampa",
        "property_name": "The Standard at Tampa",
        "url": "https://thestandardtampa.landmark-properties.com/",
    },
    {
        "id": "02_halo_46",
        "property_name": "Halo 46",
        "url": "https://www.halo46studentliving.com/amenities/",
    },
    {
        "id": "03_hub_on_campus_tampa",
        "property_name": "Hub On Campus Tampa",
        "url": "https://huboncampus.com/tampa/amenities/",
    },
    {
        "id": "04_the_province_tampa",
        "property_name": "The Province Tampa",
        "url": "https://www.americancampus.com/student-apartments/fl/tampa/the-province-tampa",
    },
    {
        "id": "05_avalon_heights",
        "property_name": "Avalon Heights",
        "url": "https://www.americancampus.com/student-apartments/fl/tampa/avalon-heights",
    },
    {
        "id": "06_4050_lofts",
        "property_name": "4050 Lofts",
        "url": "https://www.4050lofts.com/apartments/fl/tampa/amenities",
    },
    {
        "id": "07_venue_at_north_campus",
        "property_name": "Venue at North Campus",
        "url": "https://venueatnorthcampus.prospectportal.com/tampa/venue-at-north-campus/amenities/",
    },
    {
        "id": "08_station_42",
        "property_name": "Station 42",
        "url": "https://station42.us/amenities/",
    },
    {
        "id": "09_42n_apartments",
        "property_name": "42N Apartments",
        "url": "https://www.live42n.com/amenities/",
    },
    {
        "id": "10_the_ivy",
        "property_name": "The Ivy",
        "url": "https://www.livetheivy.com/apartments/fl/tampa/amenities",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Tags whose content should be stripped entirely (not just the tag)
_NOISE_TAGS = {"script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"}

DOCUMENTS_DIR = Path(__file__).parent / "documents"


def _clean_text(soup: BeautifulSoup) -> str:
    """Remove boilerplate tags and return collapsed plain text."""
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    raw = soup.get_text(separator="\n")
    # Collapse runs of blank lines into a single blank line
    lines = [ln.strip() for ln in raw.splitlines()]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return cleaned.strip()


def fetch_document(source: dict) -> dict:
    """Fetch one source URL and return a document record."""
    url = source["url"]
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [ERROR] Could not fetch {url}: {exc}")
        return {
            "property_name": source["property_name"],
            "url": url,
            "raw_text": "",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "fetch_error": str(exc),
        }

    soup = BeautifulSoup(response.text, "lxml")
    raw_text = _clean_text(soup)
    char_count = len(raw_text)

    print(f"  [OK]    {source['property_name']} — {char_count:,} chars")
    return {
        "property_name": source["property_name"],
        "url": url,
        "raw_text": raw_text,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "fetch_error": None,
    }


def save_document(doc: dict, doc_id: str) -> Path:
    """Write a document record to documents/<id>.json."""
    out_path = DOCUMENTS_DIR / f"{doc_id}.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main():
    DOCUMENTS_DIR.mkdir(exist_ok=True)

    print(f"Ingesting {len(SOURCES)} sources into {DOCUMENTS_DIR}/\n")
    success, failed = 0, 0

    for source in SOURCES:
        print(f"Fetching: {source['property_name']}")
        doc = fetch_document(source)
        path = save_document(doc, source["id"])

        if doc["fetch_error"]:
            failed += 1
        else:
            success += 1

        print(f"  Saved -> {path.name}")
        time.sleep(1)  # be polite between requests

    print(f"\nDone. {success} succeeded, {failed} failed.")
    if failed:
        print("Re-run or manually add raw text for any failed sources before chunking.")


if __name__ == "__main__":
    main()
