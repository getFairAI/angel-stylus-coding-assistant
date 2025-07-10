import pandas as pd
import json

def parse_stylus_dataset():
    with open('./data/stylus-dataset.json', 'r') as file:
        content = file.read()
        file.close()
    examples = list(json.loads(content))
    titles_list = []
    instructions_list = []
    responses_list = []
    for example in examples:
        titles_list.append(f"{example['category']} - {example['metadata']['features']}")
        instructions_list.append(example['instruction'])
        responses_list.append(example['code'])
    
    final_data = {
        'Instruction': instructions_list,
        'Title': titles_list,
        'Response': responses_list 
    }
    dataframe = pd.DataFrame(final_data)
    dataframe.to_csv('./data/stylus-examples-2.csv')
    
def parse_artifical_data_set():
    with open('./data/artificial-data-set.md', 'r') as file:
        content = file.read()
        file.close()
    
    examples = content.split('## ')
    
    titles_list = []
    instructions_list = []
    responses_list = []

    # skip first elemetn as it is the document title
    for example in examples[1:]:
        [ title, data] = example.split('**Instruction**:')
        [ instruction, code ] = data.split('**code**:')
        titles_list.append(title)
        instructions_list.append(instruction)
        code = code.replace("```rust", "")
        code = code.replace("```\n", "")
        responses_list.append(code)
    
    final_data = {
        'Instruction': instructions_list,
        'Title': titles_list,
        'Response': responses_list 
    }
    dataframe = pd.DataFrame(final_data)
    dataframe.to_csv('./data/styus-examples.csv')
    
def parse_rig_data_set():
    with open('./data/rig-data-set.json', 'r') as file:
        content = file.read()
        file.close()
    examples = list(json.loads(content))
    titles_list = []
    instructions_list = []
    responses_list = []
    for example in examples:
        titles_list.append(f"{example['metadata']['description']}")
        instructions_list.append(example['instruction'])
        responses_list.append(example['code'])
    
    final_data = {
        'Instruction': instructions_list,
        'Title': titles_list,
        'Response': responses_list 
    }
    dataframe = pd.DataFrame(final_data)
    dataframe.to_csv('./data/rig-examples.csv')
    
def main():
    return    
    
    
if __name__ == "__main__":
    parse_rig_data_set()