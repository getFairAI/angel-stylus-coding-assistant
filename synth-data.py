import json
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import MarkdownTextSplitter
from langchain_community.llms.ollama import Ollama
import time

def generate_questions_answers(text_chunks):
    messages = [
    {'role': 'system', 'content': 'You are an expert API that converts bodies of text into questions and answers in JSON format. Generate up to 3 complex question and answer sets. IMMPORTANT: ONLY GENERATE QUESTION AND ANSWER SET. Your response should be an array and each JSON " \
    "should contain a single question with a single answer.\n.'},
    {'role': 'user', 'content': 'Text: ' + text_chunks}
    ]

    try:
        #model = Ollama(model="mistral")
        model = Ollama(model="llama3.3", temperature=0.9)
        response_text = model.invoke(messages)
        list_data = list(json.loads(response_text))
        str_list = [f"{json.dumps(el)}\n" for el in list_data]
        with open("./data/q&a_arbitrum.jsonl", "a") as file:
            file.writelines(str_list)
            file.close()
        
        return response_text
    except json.JSONDecodeError:
        print(response_text)
        print("Error: Response is not valid JSON.... Trying to fix the JSON.")
        # fix_json(json.loads(response_text))
        return []

def by_stylus(page: str):
    try:
        return page.index("Stylus by Example") >= 0
    except:
        return False

def by_not_stylus(page: str):
    try:
        page.index("Stylus by Example")
        return False
    except ValueError:
        return True

def clean_toml_code(page: str):
    return page.split("### Cargo.toml")[0]
    
# generate q&a from documentation
def main():
    start_chunk = 0
    with open("./data/synth-status-arbitrum", "r") as status:
        start_chunk = int(status.read()) + 1
        status.close()
    with open("./data/documentation.md", "r") as file:
        content = file.read()
        file.close()
    # create documents per page
    pages = content.split('\n\n---\n\n')
    text_splitter = MarkdownTextSplitter(chunk_size=2000, chunk_overlap=200)
    print(len(pages))
    stylus_content_pages = list(filter(by_not_stylus, pages))
    print(len(stylus_content_pages))
    #stylus_content_pages = list(map(clean_toml_code, stylus_content_pages))
    chunks = text_splitter.create_documents(stylus_content_pages)
    
    # start from "start_chunk" index
    print(f"Starting from chunk: {start_chunk}\nMissing chunks: {len(chunks[start_chunk:])}")
    for i, chunk in enumerate(chunks[start_chunk:]):
        #slice_chunks = chunks[i::i+3]
        # slice_chunks = '\n '.join([str(x) for x in slice_chunks])
        start_time = time.time()
        generate_questions_answers(chunk.page_content)
        end = time.time() - start_time
        print(f"Finished chunk {i + start_chunk} in {end} seconds")
        print(f"Estimated Tiem remaining: {end * len(chunks[i:])/ 60} min")
        with open('synth-status-arbitrum', 'w') as f:
            f.write(f"{i+start_chunk}")
            f.close()
        

if __name__ == "__main__":
    main()