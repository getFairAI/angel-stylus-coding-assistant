from playwright.sync_api import sync_playwright
import json
from datetime import datetime
import re
import json
from typing import List
from chromadb import Documents, EmbeddingFunction, Embeddings
import ollama
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import time

ARCHIVE_URL = "https://stylus-saturdays.com/archive"

CATEGORIES = {
    "Tutorial": [
        "A detailed step-by-step developer tutorial",
        "A how-to guide for building or using Stylus tools"
    ],
    "Interview": [
        "An interview or conversation with a Stylus ecosystem developer",
        "Insights from developers on Stylus projects"
    ],
    "Ecosystem Update": [
        "Periodic update on Stylus ecosystem news",
        "Recap of events, releases, and community highlights"
    ],
    "Tooling Guide": [
        "A technical guide focused on tooling and SDK usage",
        "Instructions for specific Stylus tooling workflows"
    ],
    "News/Recap": [
        "General news and updates about Stylus Saturdays topics",
        "Recap of Stylus community events and announcements"
    ]
}


def embed(text):
    return ollama.embeddings(
        model="nomic-embed-text",
        prompt=text
    )["embedding"]


def build_category_vectors() -> dict[str, np.ndarray]:
    """
    Build a prototype embedding for each category by
    averaging the embeddings of its descriptive phrases.
    """
    cat_vectors = {}
    for cat, descs in CATEGORIES.items():
        desc_embs = [embed(desc) for desc in descs]
        cat_vectors[cat] = np.mean(np.vstack(desc_embs), axis=0)
    return cat_vectors


# Precompute once
CATEGORY_VECTORS = build_category_vectors()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b)
    return float(np.dot(a_norm, b_norm))


def classify_title(title):
    """
    Returns tuple: (best_category, best_similarity_score)
    """
    title_emb = embed(title)
    scores = []
    best_cat, best_score = None, -1.0

    for cat, cat_vec in CATEGORY_VECTORS.items():
        score = cosine_similarity(np.array(title_emb), cat_vec)
        scores.append({cat: score})
        if score > best_score:
            best_cat, best_score = cat, score

    return best_cat, best_score


def get_post_links(page):
    page.goto(ARCHIVE_URL)
    page.wait_for_timeout(5000)

    links = []
    for a in page.query_selector_all("a"):
        href = a.get_attribute("href")
        if href and "/p/" in href:
            link = href.split("?")[0]
            if link.startswith("/"):
                link = "https://stylus-saturdays.com" + link
            links.append(link)
    return list(set(links))


def extract_hidden_tags(page):
    """
    Attempt to extract tags from internal JSON state if present.
    Substack often embeds initial state in <script> tags.
    """
    script_texts = page.eval_on_selector_all(
        "script",
        "nodes => nodes.map(n => n.innerText)"
    )
    tags = []
    for text in script_texts:
        if "tags" in text.lower():
            # Look for JSON block in script text
            m = re.search(r"\{.*?\"tags\":\s*\[.*?\].*?\}", text, re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group(0))
                    # Extract tags if present
                    if 'tags' in obj and isinstance(obj['tags'], list):
                        tags += obj['tags']
                except:
                    continue
    # Deduplicate
    return list(set(tags))


def extract_published_date_from_rendered_text(page):
    # Grab the rendered article text (body + headers)
    content = page.inner_text("article")  # entire article DOM text

    # Look for a plausible date pattern, e.g.:
    #   Jan 02, 2025   or   20th April, 2025   or   Sept 7, 2024
    patterns = [
        r"\b([A-Za-z]{3,9}\s\d{1,2},\s\d{4})",          # "Aug 01, 2025"
        r"\b(\d{1,2}(?:st|nd|rd|th)\s[A-Za-z]+,\s\d{4})"  # "20th April, 2025"
    ]

    for pat in patterns:
        m = re.search(pat, content)
        if m:
            raw_date = m.group(1)
            try:
                # Try to parse the human format to ISO
                # e.g. "Aug 01, 2025"
                return datetime.strptime(raw_date, "%b %d, %Y").date().isoformat()
            except ValueError:
                try:
                    return datetime.strptime(raw_date, "%d%th %B, %Y").date().isoformat()
                except:
                    # Fallback to raw date if parsing fails
                    return raw_date

    # If nothing matched
    return ""


def scrape_post(page, url):
    # navigate and wait for the DOM to be ready
    page.goto(url, wait_until="domcontentloaded")

    # wait for the article element to be present
    page.wait_for_selector("article", timeout=60000)

    # extract title more robustly via locator
    title_locator = page.locator("article h1")
    visible_titles = [t for t in title_locator.all_text_contents() if t.strip()]

    title = visible_titles[0]

    # extract the published date text (with your helper)
    date = extract_published_date_from_rendered_text(page)

    # extract article paragraphs
    body_locator = page.locator("article div p, article div h2, article div h3")
    all_texts = body_locator.all_text_contents()
    text = "\n".join([t.strip() for t in all_texts if t.strip()])

    # classify title
    category, score = classify_title(title)

    return {
        "text": text,
        "metadata": {
            "source": "stylus_saturdays",
            "url": url,
            "title": title.strip(),
            "published_date": date,
            "category": category,
            "content_type": "blog"
        }
    }

def scrape_all():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        post_links = get_post_links(page)
        print(f"Found {len(post_links)} posts")

        results = []
        for link in post_links:
            try:
                data = scrape_post(page, link)
                results.append(data)
            except Exception as e:
                print("Error scraping", link, e)

        browser.close()

    with open("data/stylus_saturdays.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    scrape_all()
