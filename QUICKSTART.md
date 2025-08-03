# Quick Start Guide - Angel Stylus Coding Assistant with MCP

Get the MCP-enabled Angel Stylus Coding Assistant up and running in minutes!

## Prerequisites

1. **Python 3.9+** - [Download here](https://python.org/downloads/)
2. **Ollama** (optional, for LLM functionality) - [Download here](https://ollama.ai/)

## Quick Setup (Automatic)

### Option 1: One-Click Start (Recommended)

**For Linux/macOS:**
```bash
./start.sh
```

**For Windows:**
```batch
start.bat
```

### Option 2: Manual Python Run
```bash
python3 run_mcp_assistant.py
```

This will automatically:
- ✅ Check Python version
- ✅ Install dependencies
- ✅ Set up required directories
- ✅ Initialize the ChromaDB database
- ✅ Check Ollama installation
- 🎯 Present menu options to run the assistant

## What You'll See

```
🤖 Angel Stylus Coding Assistant with MCP Support
============================================================
✅ Python version: 3.11.x
✅ Created directory: mcp_contexts
✅ Created directory: logs  
✅ Created directory: chroma_db
📦 Installing dependencies...
✅ Dependencies installed successfully!
🗄️  Setting up database...
✅ Database setup completed
✅ Ollama is installed and running
Available models:
  - llama3.1:8b
  - deepseek-r1:7b

============================================================
🎯 What would you like to do?
1. Run API server (http://localhost:8001)
2. Run web interface (http://localhost:8501)  
3. Run both API server and web interface
4. Test MCP functionality
5. Run API client example
6. Exit
```

## Usage Options

### 1. Web Interface (Easiest)
- Choose option **2** or **3**
- Open browser to `http://localhost:8501`
- Start chatting with the MCP-enabled assistant!

### 2. API Server
- Choose option **1** or **3**  
- API available at `http://localhost:8001`
- Use the provided client examples or your own HTTP client

### 3. Test MCP Functionality
- Choose option **4**
- Runs automated tests to verify MCP context retention works

## First Conversation Example

**User:** "What is Stylus?"

**Assistant:** "Stylus is a framework for writing Arbitrum smart contracts in Rust..."

**User:** "How do I install it?" *(Note: Assistant remembers the previous context)*

**Assistant:** "To install Stylus (which we just discussed), you can..."

The assistant now remembers your conversation and provides contextual responses!

## Manual Setup (If Needed)

If the automatic setup doesn't work:

1. **Install dependencies:**
   ```bash
   pip install -r requirements_mcp.txt
   ```

2. **Setup database:**
   ```bash  
   python setup_database.py
   ```

3. **Install Ollama models:**
   ```bash
   ollama pull llama3.1:8b
   ollama pull deepseek-r1:7b
   ```

4. **Run the assistant:**
   ```bash
   python main.py  # For API server
   # OR
   streamlit run pages/assistant.py  # For web interface
   ```

## Troubleshooting

### "Ollama not found"
- Install Ollama from https://ollama.ai/
- Pull at least one model: `ollama pull llama3.1:8b`

### "Module not found" errors
- Run: `pip install -r requirements_mcp.txt`
- Ensure you're using Python 3.9+

### Database issues
- Delete `chroma_db` folder and run setup again
- Run: `python setup_database.py`

### Port already in use
- Change ports in the startup script
- Or kill existing processes on ports 8001/8501

## What Makes This Special?

🧠 **Memory**: Unlike regular chatbots, this assistant remembers your conversation
🔄 **Context**: References to "it", "that", "the previous example" work perfectly  
📚 **Knowledge**: Built on official Stylus documentation
🔧 **Flexible**: Use via web interface, API, or integrate into your own apps

## Next Steps

- Read [MCP_README.md](MCP_README.md) for detailed MCP implementation
- Check [README.md](README.md) for complete project documentation  
- Explore the API with [mcp_api_client.py](mcp_api_client.py)

Happy coding with Stylus! 🚀 