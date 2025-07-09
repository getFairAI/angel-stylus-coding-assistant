import ollama
from aux_functions import find_closest_match_smart

VALID_FILTER_KEYS = [
    "category",
    "subsection"
]

VALID_SECTIONS_BY_CATEGORY = {
    "Introduction": [
        "In a nutshell",
        "What's Stylus?",
        "Use Cases",
        "Getting Started"
    ],
   "Quickstart": [
        "Setting up your development environment",
        "Creating a Stylus project with cargo stylus",
        "Checking the validity of your contract",
        "Deploying your contract",
        "Exporting your contract's ABIs",
        "Calling your contract",
        "Sending a transaction to your contract"
    ],
    "Rust SDK": [
        "Overview",
        "Structure of a Contract",
        "Hello World",
        "Primitive Data Types",
        "Variables",
        "Constants",
        "Function",
        "Errors",
        "Events",
        "Inheritance",
        "Vm Affordances",
        "Sending Ether",
        "Function Selector",
        "Abi Encode",
        "Abi Decode",
        "Hashing",
        "Bytes In Bytes Out",
        "Advanced features",
        "Use Rust Crates"
    ],
    "Rust CLI": [
        "Overview",
        "Debug transactions",
        "Testing contracts",
        "Verify contracts",
        "Cache contracts",
        "Verify on Arbiscan",
        "Optimize WASM binaries"
    ],
    "Concepts": [
        "Architecture overview",
        "Gas metering"
    ],
    "Examples": [
        "Erc20",
        "Erc721",
        "Multi Call",
        "Vending Machine"
    ],    
    "Using other languages": [],
    "Troubleshooting": []
}
    
def validate_filters(raw_filters):
    validated = {}

    for raw_key, raw_value in raw_filters.items():
        # Validate key first (fuzzy match to known keys)
        key = find_closest_match_smart(raw_key, VALID_FILTER_KEYS)
        print("key", key)
        if key is None:
            continue  # skip unrecognized keys
        
        # Validate value depending on key
        if key == "category":
            match = find_closest_match_smart(raw_value, list(VALID_SECTIONS_BY_CATEGORY.keys()))
        elif key == "subsection":
            category = validated.get("category") or raw_filters.get("category")
            valid_subsections = VALID_SECTIONS_BY_CATEGORY.get(category, [])
            match = find_closest_match_smart(raw_value, valid_subsections)
        else:
            match = raw_value

        if match:
            validated[key] = match

    return validated

