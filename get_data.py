import requests
from bs4 import BeautifulSoup
import json


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
    }
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


def clean_page_content(url):
    res = requests.get(url)
    if res.status_code != 200:
        print(f"Failed to fetch {url}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    # get the main class that contains the content
    main = soup.select_one("article")
    if not main:
        print(f"Could not locate main content in {url}")
        return None

    # Remove not necessary content
    for tag in main.select(".table-of-contents, .edit-page-link, nav, footer"):
        tag.decompose()

    # get the relevant text
    parts = []
    for elem in main.find_all(["h1", "h2", "h3", "p", "ul", "ol", "pre", "summary"]):
        text = elem.get_text(separator=" ", strip=True)
        if text:
            parts.append(text)

    return "\n\n".join(parts)


documents = []

for page in pages:
    content = clean_page_content(page["url"])
    if content:
        metadata = {
            "category": page["category"]
        }
        if "subsection" in page:
            metadata["subsection"] = page["subsection"]
        
        doc = {
            "text": content,
            "metadata": metadata
        }
        documents.append(doc)

#build data file
with open("data/stylus_docs.json", "w", encoding="utf-8") as f:
    json.dump(documents, f, ensure_ascii=False, indent=2)

print(f"✅ Saved {len(documents)} documents to stylus_docs.json")
