"""
Ingestion for LearnWeb3 Arbitrum Stylus course text content (excluding videos).
Scrapes lesson pages, extracts transcript/lesson text, and stores as JSON for RAG.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

COURSE_BASE = "https://learnweb3.io/courses/arbitrum-stylus-course/"
OUTPUT_JSON_PATH = "data/stylus_course.json"

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def fetch_html(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[warn] Failed to fetch {url}: {e}")
        return None


def find_lesson_links(course_soup: BeautifulSoup) -> List[str]:
    """Collect all lesson links that belong to the course."""
    links = set()
    for a in course_soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http"):
            url = href
        else:
            url = urljoin(COURSE_BASE, href)

        parsed = urlparse(url)
        # Accept only links under the course path and likely lessons (contain '/lessons/' or end with a slug)
        if "learnweb3.io" in parsed.netloc and "arbitrum-stylus-course" in parsed.path:
            # crude lesson heuristic
            if "/lessons/" in parsed.path or parsed.path.rstrip("/").split("/")[-1]:
                links.add(url.rstrip("/") + "/")
    return sorted(links)


def extract_main_text(soup: BeautifulSoup) -> str:
    """
    Extract readable text from a lesson page, skipping videos/iframes and nav/footer.
    """
    for tag in soup.find_all(["video", "iframe", "source", "script", "style", "nav", "footer"]):
        tag.decompose()

    # Prefer article, then main, then largest div
    container = soup.find("article") or soup.find("main")
    if not container:
        divs = soup.find_all("div")
        container = max(divs, key=lambda d: len(d.get_text(strip=True)), default=soup)

    text = container.get_text("\n\n", strip=True)
    return text


def build_entry(url: str, title: str, body: str) -> Dict[str, Any]:
    now_iso = datetime.utcnow().isoformat() + "Z"
    return {
        "text": f"Source: LearnWeb3 Arbitrum Stylus Course\nURL: {url}\nTitle: {title}\n\n{body}",
        "metadata": {
            "source": "learnweb3_stylus_course",
            "url": url,
            "title": title,
            "ingested_at": now_iso,
        },
    }


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def ingest_stylus_course():
    entries: List[Dict[str, Any]] = []

    course_soup = fetch_html(COURSE_BASE)
    if not course_soup:
        print("[warn] Could not fetch course landing page; aborting")
        return 0

    lesson_urls = find_lesson_links(course_soup)
    print(f"[info] Found {len(lesson_urls)} potential lesson pages")

    for url in lesson_urls:
        soup = fetch_html(url)
        if not soup:
            continue

        title_tag = soup.find(["h1", "title"])
        title = title_tag.get_text(strip=True) if title_tag else url

        body = extract_main_text(soup)
        if not body:
            print(f"[warn] Empty body for {url}")
            continue

        entries.append(build_entry(url, title, body))

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[✔] Saved {len(entries)} course entries to {OUTPUT_JSON_PATH}")
    return len(entries)


if __name__ == "__main__":
    ingest_stylus_course()
