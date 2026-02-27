"""
Ingest OpenZeppelin Stylus Contracts docs for RAG.
Source: https://docs.openzeppelin.com/contracts-stylus
Strategy: crawl pages under the contracts-stylus path (same domain), strip nav/video/iframes,
and store readable text with metadata.
"""

import json
import os
from collections import deque
from datetime import datetime
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import load_entries, merge_entries

BASE_URL = "https://docs.openzeppelin.com/contracts-stylus"
OUTPUT_JSON_PATH = "data/openzeppelin_stylus_docs.json"

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"
}

MAX_PAGES = 60  # safety cap to avoid runaway crawls


def fetch_html(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def is_valid_link(base_netloc: str, href: str) -> bool:
    if not href:
        return False
    parsed = urlparse(href)
    if parsed.scheme and parsed.netloc and parsed.netloc != base_netloc:
        return False
    # ensure we're staying under contracts-stylus section
    path = parsed.path or ""
    return "contracts-stylus" in path


def discover_links(start_url: str) -> List[str]:
    parsed_base = urlparse(start_url)
    netloc = parsed_base.netloc

    seen: Set[str] = set()
    queue = deque([start_url])
    ordered: List[str] = []

    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)

        try:
            soup = fetch_html(url)
        except Exception as e:
            write_ingestion_log(f"[warn] Failed to fetch {url}: {e}")
            continue

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#"):
                continue
            full = urljoin(url, href)
            if is_valid_link(netloc, full) and full not in seen:
                queue.append(full)

    write_ingestion_log(f"[info] Discovered {len(ordered)} pages (cap {MAX_PAGES})")
    return ordered


def extract_main_text(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(["script", "style", "video", "iframe", "nav", "footer"]):
        tag.decompose()

    container = soup.find("article") or soup.find("main")
    if not container:
        # choose largest text div fallback
        divs = soup.find_all("div")
        container = max(divs, key=lambda d: len(d.get_text(strip=True)), default=soup)

    text = container.get_text("\n\n", strip=True)
    return text


def build_entry(url: str, title: str, body: str) -> Dict:
    now_iso = datetime.utcnow().isoformat() + "Z"
    return {
        "text": f"Source: OpenZeppelin Stylus Docs\nURL: {url}\nTitle: {title}\n\n{body}",
        "metadata": {
            "source": "openzeppelin_stylus_docs",
            "url": url,
            "title": title,
            "ingested_at": now_iso,
        },
    }


def ingest_openzeppelin_stylus_docs(output_path: str = OUTPUT_JSON_PATH) -> int:
    entries: List[Dict] = []
    page_urls = discover_links(BASE_URL)

    for url in page_urls:
        try:
            soup = fetch_html(url)
        except Exception as e:
            write_ingestion_log(f"[warn] Skip {url}: {e}")
            continue

        title_tag = soup.find(["h1", "title"])
        title = title_tag.get_text(strip=True) if title_tag else url

        body = extract_main_text(soup)
        if not body:
            write_ingestion_log(f"[warn] Empty body at {url}")
            continue

        entries.append(build_entry(url, title, body))

    existing = load_entries(output_path)
    merged, stats = merge_entries(
        existing, entries, key_fn=lambda e: e.get("metadata", {}).get("url")
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    write_ingestion_log(
        f"[ok] Saved {len(merged)} OZ Stylus docs (added {stats['added']}, updated {stats['updated']}, unchanged {stats['unchanged']}, retained {stats['retained']}) to {output_path}"
    )
    return len(merged)


if __name__ == "__main__":
    ingest_openzeppelin_stylus_docs()
