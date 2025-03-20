import pandas as pd


def parse_artifical_data_set():
    with open('./artificial-data-set.md', 'r') as file:
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
    dataframe.to_csv('styus-examples.csv')
    
def parse_rig_data_set():
    pd.read_json('./rig-data-set.json')
    
def main():
    return    
    
    
if __name__ == "__main__":
    parse_artifical_data_set()