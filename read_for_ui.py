def read_for_ui(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
        file.close()
    return content
  
if __name__ == "__main__":
    read_for_ui()