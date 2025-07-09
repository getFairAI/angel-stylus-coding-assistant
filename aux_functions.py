import json
import re
from fuzzywuzzy import process as fuzzy_process
from fuzzywuzzy import fuzz

def find_closest_match(input_string, array_of_strings):
    closest_match, score = fuzzy_process.extractOne(input_string, array_of_strings)
    return closest_match, score

def find_all_matches(input_string, array_of_strings, limit=5):
    matches = fuzzy_process.extract(input_string, array_of_strings, limit=limit)
    return matches

def find_closest_match_smart(input_string, array_of_strings):
    valid_string = str(input_string)
    
    if not valid_string or not array_of_strings:
        return None
    try:
        if len(valid_string) < 4:
            closest_match, score = fuzzy_process.extractOne(valid_string, array_of_strings, scorer=fuzz.token_sort_ratio) # Avoid confusion with small words
            return closest_match if score >= 75 else None
        closest_match, score = fuzzy_process.extractOne(valid_string, array_of_strings)
        return closest_match if score >= 75 else None
    except Exception as e:
        print("Error using fuzzy search: ", e)
        return None

def get_json_from_llm(string_json_raw):
    json_str = re.search(r'{.*}', string_json_raw, re.DOTALL).group()
    json_data = json.loads(json_str)
    return json_data

def remove_think_tags(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()