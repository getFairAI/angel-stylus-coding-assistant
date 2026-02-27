import requests
from bs4 import BeautifulSoup
import json
import os

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import load_entries, merge_entries


# -----------------------------
# Pages definition (unchanged)
# -----------------------------
rust_sdk_pages = [
    {
        "url": "https://docs.arbitrum.io/stylus/reference/overview",
        "category": "Rust SDK",
        "subsection": "Overview"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/reference/project-structure",
        "category": "Rust SDK",
        "subsection": "Structure of a Contract"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/hello_world",
        "category": "Rust SDK",
        "subsection": "Hello World"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/primitive_data_types",
        "category": "Rust SDK",
        "subsection": "Primitive Data Types"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/variables",
        "category": "Rust SDK",
        "subsection": "Variables"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/constants",
        "category": "Rust SDK",
        "subsection": "Constants"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/function",
        "category": "Rust SDK",
        "subsection": "Function"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/errors",
        "category": "Rust SDK",
        "subsection": "Errors"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/events",
        "category": "Rust SDK",
        "subsection": "Events"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/inheritance",
        "category": "Rust SDK",
        "subsection": "Inheritance"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/vm_affordances",
        "category": "Rust SDK",
        "subsection": "Vm Affordances"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/sending_ether",
        "category": "Rust SDK",
        "subsection": "Sending Ether"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/function_selector",
        "category": "Rust SDK",
        "subsection": "Function Selector"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/abi_encode",
        "category": "Rust SDK",
        "subsection": "Abi Encode"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/abi_decode",
        "category": "Rust SDK",
        "subsection": "Abi Decode"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/hashing",
        "category": "Rust SDK",
        "subsection": "Hashing"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/basic_examples/bytes_in_bytes_out",
        "category": "Rust SDK",
        "subsection": "Bytes In Bytes Out"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/reference/rust-sdk-guide",
        "category": "Rust SDK",
        "subsection": "Advanced features"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/recommended-libraries",
        "category": "Rust SDK",
        "subsection": "Use Rust Crates"
    }
]

rust_cli_pages = [
    {
        "url": "https://docs.arbitrum.io/stylus/using-cli",
        "category": "Rust CLI",
        "subsection": "Overview"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/how-tos/debugging-tx",
        "category": "Rust CLI",
        "subsection": "Debug transactions"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/how-tos/testing-contracts",
        "category": "Rust CLI",
        "subsection": "Testing contracts"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/how-tos/verifying-contracts",
        "category": "Rust CLI",
        "subsection": "Verify contracts"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/how-tos/caching-contracts",
        "category": "Rust CLI",
        "subsection": "Cache contracts"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/how-tos/verifying-contracts-arbiscan",
        "category": "Rust CLI",
        "subsection": "Verify on Arbiscan"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/how-tos/optimizing-binaries",
        "category": "Rust CLI",
        "subsection": "Optimize WASM binaries"
    }
]

concepts_pages = [
    {
        "url": "https://docs.arbitrum.io/stylus/concepts/how-it-works",
        "category": "Concepts",
        "subsection": "Architecture overview"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/concepts/gas-metering",
        "category": "Concepts",
        "subsection": "Gas metering"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/gentle-introduction",
        "category": "A gentle introduction"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/quickstart",
        "category": "Quickstart"
    },
]

examples_pages = [
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/applications/erc20",
        "category": "Examples",
        "subsection": "Erc20"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/applications/erc721",
        "category": "Examples",
        "subsection": "Erc721"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/applications/multi_call",
        "category": "Examples",
        "subsection": "Multi Call"
    },
    {
        "url": "https://docs.arbitrum.io/stylus-by-example/applications/vending_machine",
        "category": "Examples",
        "subsection": "Vending Machine"
    }
]

extra_pages = [
    {
        "url": "https://docs.arbitrum.io/stylus/how-tos/adding-support-for-new-languages",
        "category": "Using other languages"
    },
    {
        "url": "https://docs.arbitrum.io/stylus/troubleshooting-building-stylus",
        "category": "Troubleshooting"
    }
]

pages = rust_sdk_pages + rust_cli_pages + concepts_pages + examples_pages + extra_pages


# -----------------------------
# Helpers
# -----------------------------
def clean_page_content(url):
    res = requests.get(url)
    if res.status_code != 200:
        write_ingestion_log(f"[warn] Failed to fetch {url}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    main = soup.select_one("article")
    if not main:
        write_ingestion_log(f"[warn] Could not locate main content in {url}")
        return None

    for tag in main.select(".table-of-contents, .edit-page-link, nav, footer"):
        tag.decompose()

    parts = []
    for elem in main.find_all(["h1", "h2", "h3", "p", "ul", "ol", "pre", "summary"]):
        text = elem.get_text(separator=" ", strip=True)
        if text:
            parts.append(text)

    return "\n\n".join(parts)


# -----------------------------
# MAIN INGESTION FUNCTION
# -----------------------------
def ingest_stylus_docs(output_path="data/stylus_docs.json"):
    documents = []
    existing = load_entries(output_path)

    for page in pages:
        content = clean_page_content(page["url"])
        if not content:
            continue

        metadata = {
            "category": page["category"],
            "url": page["url"],
        }
        if "subsection" in page:
            metadata["subsection"] = page["subsection"]

        title_parts = ["Documentation"]

        if page.get("category"):
            title_parts.append(page["category"])

        if page.get("subsection"):
            title_parts.append(page["subsection"])

        header_title = " - ".join(title_parts)
        final_text = f"{header_title}\n\n{content}"

        documents.append(
            {
                "text": final_text,
                "metadata": metadata
            }
        )

    merged, stats = merge_entries(
        existing,
        documents,
        key_fn=lambda e: e.get("metadata", {}).get("url"),
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    write_ingestion_log(
        f"[ok] Saved {len(merged)} docs (added {stats['added']}, updated {stats['updated']}, unchanged {stats['unchanged']}, retained {stats['retained']}) to {output_path}"
    )
    return len(merged)


# -----------------------------
# Standalone execution
# -----------------------------
if __name__ == "__main__":
    ingest_stylus_docs()
