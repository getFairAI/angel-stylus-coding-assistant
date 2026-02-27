"""
Ingestion for LearnWeb3 Arbitrum Stylus course text content (excluding videos).
Uses Playwright to render Next.js pages and extract lesson transcripts/text.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Set
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    load_entries,
    merge_entries,
    record_ingestion_stats,
    should_skip_ingestion,
)

COURSE_BASE = "https://learnweb3.io/courses/arbitrum-stylus-course/"
OUTPUT_JSON_PATH = "data/stylus_course.json"
JOB_NAME = "stylus_course"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def extract_slugs_from_next_data(obj) -> Set[str]:
    slugs: Set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            if "slug" in o and isinstance(o["slug"], str):
                slugs.add(o["slug"])
            if "lessons" in o and isinstance(o["lessons"], list):
                for item in o["lessons"]:
                    if isinstance(item, dict) and "slug" in item:
                        slugs.add(item["slug"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return slugs


def get_lesson_urls(page) -> List[str]:
    page.goto(COURSE_BASE, wait_until="networkidle")
    data = page.evaluate("() => window.__NEXT_DATA__")
    slugs = extract_slugs_from_next_data(data) if data else set()
    if not slugs:
        write_ingestion_log("[warn] No lesson slugs found in __NEXT_DATA__")
    urls = [
        urljoin(COURSE_BASE, f"{slug}/")
        for slug in sorted(slugs)
        if "module-" in slug.lower()
    ]
    return urls


def scrape_lesson(page, url: str) -> Dict[str, Any]:
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(500)  # allow client-side hydration

    title = ""
    try:
        title = page.locator("main h1").first.inner_text().strip()
    except Exception:
        try:
            title = page.title().strip()
        except Exception:
            title = url

    # Remove media elements to avoid video transcripts
    page.eval_on_selector_all("video, iframe, source", "els => els.forEach(e => e.remove())")

    body_text = ""
    for selector in ["main", "article", "body"]:
        try:
            body_text = page.locator(selector).inner_text().strip()
            if body_text:
                break
        except Exception:
            continue

    now_iso = datetime.utcnow().isoformat() + "Z"
    return {
        "text": f"Source: LearnWeb3 Arbitrum Stylus Course\nURL: {url}\nTitle: {title}\n\n{body_text}",
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
def ingest_stylus_course(force_refresh: bool = False):
    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return 0

    entries: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        lesson_urls = get_lesson_urls(page)
        write_ingestion_log(f"[info] Found {len(lesson_urls)} lesson pages")

        for url in lesson_urls:
            try:
                entry = scrape_lesson(page, url)
                if entry.get("text"):
                    entries.append(entry)
            except Exception as e:
                write_ingestion_log(f"[warn] Failed to scrape {url}: {e}")

        browser.close()

    existing = load_entries(OUTPUT_JSON_PATH)
    merged, stats = merge_entries(
        existing, entries, key_fn=lambda e: e.get("metadata", {}).get("url")
    )

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    write_ingestion_log(
        f"[ok] Saved {len(merged)} course entries (added {stats['added']}, updated {stats['updated']}, unchanged {stats['unchanged']}, retained {stats['retained']}) to {OUTPUT_JSON_PATH}"
    )
    record_ingestion_stats(JOB_NAME, stats)
    return len(merged)


if __name__ == "__main__":
    ingest_stylus_course()
