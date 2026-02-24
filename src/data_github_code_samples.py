import requests
from bs4 import BeautifulSoup
import json
import re
from typing import List
from markdownify import markdownify as md

# -------------------------------------------------------
# --- Helpers for fetching and extracting raw text -----
# -------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RAG-Scraper/1.0)"
}

def fetch_url(url: str) -> str:
    """Fetch page and return raw HTML text."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[!] Failed to fetch: {url} => {e}")
        return ""

def html_to_text(html: str) -> str:
    """Convert HTML to plain text using markdownify."""
    try:
        return md(html)
    except:
        # fallback: strip tags
        return BeautifulSoup(html, "html.parser").get_text()

# -------------------------------------------------------
# --- Step 1: Scrape the README of a GitHub repo ------
# -------------------------------------------------------

def extract_readme_links(repo_url: str) -> List[str]:
    """
    Download Awesome-Stylus README and extract all HTTP(S) links.
    """
    html = fetch_url(repo_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)

    # collect only external links and docs
    urls = []
    for a in anchors:
        href = a['href']
        # skip internal GitHub links
        if href.startswith("#"):
            continue
        if href.startswith("http"):
            urls.append(href.strip())
        else:
            # Make relative URLs absolute if needed
            if href.startswith("/"):
                urls.append("https://github.com" + href)
    return list(set(urls))

# -------------------------------------------------------
# --- Step 2: Deep scrape each individual link -------
# -------------------------------------------------------

def scrape_link(url: str) -> dict:
    """
    Crawl an external URL deeply (first-level).
    Extract title, meta, first paragraphs, and full text.
    """
    print(f"[ ] scraping: {url}")
    html = fetch_url(url)
    if not html:
        return {
            "url": url,
            "title": "",
            "metadata": {},
            "text": ""
        }

    soup = BeautifulSoup(html, "html.parser")

    # title and meta
    title = soup.title.string.strip() if soup.title else ""
    meta_desc = soup.find("meta", {"name": "description"})
    desc = meta_desc["content"].strip() if meta_desc else ""

    # main text
    text = html_to_text(html)

    return {
        "url": url,
        "title": title,
        "metadata": {
            "description": desc
        },
        "text": text
    }


# -------------------------------------------------------
# --- Step 3: Build JSON dataset object -------------
# -------------------------------------------------------

def build_dataset(repo_url: str) -> dict:
    print("[*] crawling README links")
    urls = extract_readme_links(repo_url)

    dataset = {
        "source_repo": repo_url,
        "scraped_links": []
    }

    # only scrape docs + tutorials, skip YouTube
    for link in urls:
        if any(skip in link for skip in ["youtube.com", "youtu.be"]):
            continue
        scraped = scrape_link(link)
        dataset["scraped_links"].append(scraped)

    return dataset

# -------------------------------------------------------
# --- Step 4: Run and export to JSON -------------
# -------------------------------------------------------

if __name__ == "__main__":
    REPO = "https://raw.githubusercontent.com/OffchainLabs/awesome-stylus/main/README.md"
    # fetch, crawl and dump
    result = build_dataset(REPO)

    with open("stylus_dataset.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("[*] Exported stylus_dataset.json")
