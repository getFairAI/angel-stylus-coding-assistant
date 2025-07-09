import ollama


def call_ollama(prompt, model="llama3.1"):
    try:
        response = ollama.generate(model=model, prompt=prompt.strip())
        return response['response']
    except Exception as e:
        print("Ollama error:", e)
        raise

def fallback_message():
    return (
        "I'm sorry, I couldn’t find specific information to help with that right now. "
    )

def call_llm(system_prompt, user_prompt,ollama_model = "llama3.1"):
        try:
            return call_ollama(f"{system_prompt}\n\nUser Question: {user_prompt}\nAnswer:",ollama_model)
        except:
            return fallback_message()
