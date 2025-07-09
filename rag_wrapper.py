from llm_main_wrapper import stylus_request_with_llm
from logger import log_info, log_separator
import time
from aux_functions import remove_think_tags


def stylus_chat(model_name: str, prompt: str):
    log_info(f"User started a request | Model: {model_name} | Prompt: {prompt}")
    start_time = time.time()
    result = stylus_request_with_llm(model_name, prompt)
    clean_result = remove_think_tags(result)
    duration = round(time.time() - start_time, 2)
    log_info(f"✅ Finished inference | Time: {duration}s | Output: {clean_result[:50]}...")
    log_separator()
    return clean_result


