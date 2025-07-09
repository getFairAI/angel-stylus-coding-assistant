from aux_functions import get_json_from_llm
from filters_validation import validate_filters
from llm_decider import call_llm
from logger import log_info

VALID_CATEGORIES = {
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

def format_valid_categories():
    formatted_text = "**Available categories & their respective subsections:**\n\n"
    
    for category, subsections in VALID_CATEGORIES.items():
        formatted_text += f"- **Category:** {category}\n"
        if subsections:
            formatted_text += "  - **Subsections:** " + ", ".join(subsections) + "\n"
        else:
            formatted_text += "  - (No specific subsections)\n"
    
    return formatted_text


def extract_filters(user_query):

    formatted_prompt = f"""
    You must extract relevant filters to search for Stylus documentation in the database and only return the JSON — this will be used in a pipeline, and any extra text will break the system.

    **Important Rules:**
    - Always return a JSON containing only the identifiable filters, and only that JSON (no explanations or extra text).
    - If a filter (category or subsection) cannot be confidently determined, do not include it.
    - If a **category** can be identified, include `"category"`.
    - If a **specific subsection** is clearly requested, include both `"category"` and `"subsection"`.
    - If a **subsection is mentioned but the question also asks about other options in the same category**, return only the **category**.
    - Do not invent values that are not in the list of available options.

    **Available Options:**
    - **Available categories and respective subsections:**
    {format_valid_categories()}

    **Example 1:**  
    **Question:** "How do I deploy a Stylus contract?"  
    **Expected Response:**
    {{
        "category": "Quickstart",
        "subsection": "Deploying your contract"
    }}

    **Example 2:**  
    **Question:** "What can I build with Stylus?"  
    **Expected Response:**
    {{
        "category": "Introduction",
        "subsection": "Use Cases"
    }}

    **Example 3:**  
    **Question:** "What CLI commands are available to test and deploy?"  
    **Explanation:** The user mentions multiple actions under Rust CLI — return only the category.
    **Expected Response:**
    {{
        "category": "Rust CLI"
    }}

    **Example 4:**  
    **Question:** "How do I declare variables in Stylus using Rust?"  
    **Expected Response:**
    {{
        "category": "Rust SDK",
        "subsection": "Variables"
    }}

    **Example 5:**  
    **Question:** "Show me examples of real Stylus smart contracts."  
    **Expected Response:**
    {{
        "category": "Examples"
    }}
    """
    
    #response = call_llm(formatted_prompt, user_query,"qwen2.5:32b")
    response = call_llm(formatted_prompt, user_query,"llama3.1:8b")
    return response


def get_filters_wrapper(prompt):
    raw_filters = extract_filters(prompt)
    log_info(f"🔎 Raw filters: {raw_filters}")
    try:
        json_filters = get_json_from_llm(raw_filters)
    except Exception as e:
        print("Failed to parse JSON from LLM response:", e)
        return {}
    valid_filters = validate_filters(json_filters)
    return valid_filters

#print(extract_filters("What docs do I need to travel from england to Portugal namely the microchop?"))
#print(extract_filters("do I need to microchops from england to Portugal or any more docs?"))
#filters = extract_filters("Do you have any tips for traveling from the uk to france about airplanes and other relavant stuff about travel")
#json_filters = get_json_from_llm(filters)
#print("filters - ", filters)
#print("calling filters validatinon...")
#print(validate_filters(json_filters))


#print(extract_filters("What is stylus my man?"))
#print(extract_filters("can you give me an overview for the stylus architecture?"))
#print(extract_filters("hey how do I store a transaction on Arweave?"))