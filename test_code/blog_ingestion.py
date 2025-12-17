import json
import os
from datetime import datetime
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Where we store all Stylus blog entries
BLOG_JSON_PATH = "data/stylus_blog.json"

# Tag pages we scrape for Stylus content
TAG_URLS = [
    "https://blog.arbitrum.io/tag/stylus/",
]

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"
}


# ----------------------------------------------------
# JSON loading / saving
# ----------------------------------------------------
def load_existing_entries(path: str) -> List[Dict[str, Any]]:
    """Load existing JSON entries from disk, or return empty list."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_entries(path: str, entries: List[Dict[str, Any]]) -> None:
    """Save updated entries to disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def get_known_urls(entries: List[Dict[str, Any]]) -> set:
    """Extract URL set from existing entries to avoid duplicates."""
    urls = set()
    for item in entries:
        meta = item.get("metadata", {})
        url = meta.get("url")
        if url:
            urls.add(url)
    return urls


# ----------------------------------------------------
# HTML helpers
# ----------------------------------------------------
def fetch_html(url: str) -> BeautifulSoup:
    """Fetch a URL and parse it into BeautifulSoup."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


# ----------------------------------------------------
# Extract list of post URLs from tag page
# ----------------------------------------------------
def extract_post_links_from_tag_page(tag_url: str) -> List[str]:
    """
    Extracts blog post URLs from a tag page.

    Stylus posts on the Arbitrum blog are wrapped in:
        <button class="gh-card post ..."
                onclick="window.location='/some-slug/'">

    We extract the URL from the onclick attribute.
    """
    soup = fetch_html(tag_url)
    links = set()

    # Primary extraction: look for <button> cards
    for btn in soup.find_all("button", class_=lambda c: c and "gh-card" in c and "post" in c):
        onclick = btn.get("onclick", "")
        if "window.location" not in onclick:
            continue

        # Extract the URL from the onclick string
        url_value = None

        # Support both single and double quotes
        if "'" in onclick:
            start = onclick.find("'")
            end = onclick.find("'", start + 1)
            if start != -1 and end != -1:
                url_value = onclick[start + 1:end]
        elif '"' in onclick:
            start = onclick.find('"')
            end = onclick.find('"', start + 1)
            if start != -1 and end != -1:
                url_value = onclick[start + 1:end]

        if not url_value:
            continue

        full_url = urljoin(tag_url, url_value)

        # Exclude tag pages, keep only real posts
        if "blog.arbitrum.io" in full_url and "/tag/" not in full_url:
            links.add(full_url)

    # Fallback: if somehow none were found, scan for <a> tags as backup
    if not links:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(tag_url, href)
            if "blog.arbitrum.io" in full_url and "/tag/" not in full_url:
                links.add(full_url)

    return sorted(links)


# ----------------------------------------------------
# Extract full content of a blog post
# ----------------------------------------------------
def extract_post_content(post_url: str) -> Dict[str, Any]:
    """Scrapes a blog post and extracts title, text, date, tags."""
    soup = fetch_html(post_url)

    # --- Main article area first (so we can search title inside it) ---
    article = soup.find("article")
    if article is None:
        article = soup.find("main")
    if article is None:
        # Fallback: largest <div> as post body
        candidates = soup.find_all("div")
        article = max(candidates, key=lambda d: len(d.get_text(strip=True)), default=soup)

    # --- Title (better than just the first <h1>) ---
    title = None

    # 1) Try Open Graph title if present
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()

    # 2) Try a heading inside the article itself
    if not title and article is not None:
        title_tag = article.find(["h1", "h2", "h3"])
        if title_tag:
            title = title_tag.get_text(strip=True)

    # 3) Fallback to the first <h1> on the page
    if not title:
        h1_tag = soup.find("h1")
        if h1_tag:
            title = h1_tag.get_text(strip=True)

    # 4) Absolute last fallback: use the URL as title
    if not title:
        title = post_url

    # --- Publish date (best effort) ---
    published_at = None
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        published_at = time_tag["datetime"]
    elif time_tag:
        published_at = time_tag.get_text(strip=True)

    # --- Main article content text ---
    body_text = article.get_text("\n\n", strip=True)

    # If the body starts with the title, strip it to avoid duplication
    if body_text.startswith(title):
        body_text = body_text[len(title):].lstrip()

    full_text = f"{title}\n\n{body_text}"

    return {
        "title": title,
        "text": full_text,
        "published_at": published_at,
    }



# ----------------------------------------------------
# Format into your RAG JSON structure
# ----------------------------------------------------
def build_entry(post_url: str, content: Dict[str, Any]) -> Dict[str, Any]:
    """Build a unified entry ready for Chroma ingestion."""
    return {
        "text": content["text"],
        "metadata": {
            "source": "stylus_blog",
            "url": post_url,
            "title": content["title"],
            "published_at": content.get("published_at"),
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        },
    }


# ----------------------------------------------------
# Main ingestion process
# ----------------------------------------------------
def ingest_stylus_blog():
    """Main ingestion runner."""
    # Load previous entries
    entries = load_existing_entries(BLOG_JSON_PATH)
    known_urls = get_known_urls(entries)
    print(f"[info] Loaded {len(entries)} existing blog entries")

    # Discover all post URLs across all tag pages
    all_post_urls = set()
    for tag_url in TAG_URLS:
        urls = extract_post_links_from_tag_page(tag_url)
        print(f"[info] Found {len(urls)} posts in tag page: {tag_url}")
        all_post_urls.update(urls)

    print(f"[info] Total unique post URLs discovered: {len(all_post_urls)}")

    # Fetch only new posts
    new_entries = []
    for url in sorted(all_post_urls):
        if url in known_urls:
            continue

        print(f"[new] Fetching post: {url}")
        try:
            content = extract_post_content(url)
            entry = build_entry(url, content)
            new_entries.append(entry)
            entries.append(entry)
        except Exception as e:
            print(f"[warn] Failed to extract {url}: {e}")

    # Save only if new content was found
    if new_entries:
        save_entries(BLOG_JSON_PATH, entries)
        print(f"[ok] Added {len(new_entries)} new posts to {BLOG_JSON_PATH}")
    else:
        print("[ok] No new posts found – JSON is up to date.")


if __name__ == "__main__":
    ingest_stylus_blog()
