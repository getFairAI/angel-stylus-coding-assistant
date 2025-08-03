#!/usr/bin/env python3
"""
Startup script for the MCP-enabled Angel Stylus Coding Assistant.
This script handles setup, dependency checks, and provides options to run different components.
"""

import subprocess
import sys
import os
import time
import threading
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required!")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements_mcp.txt"
        ])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def check_ollama():
    """Check if Ollama is installed and running."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama is installed and running")
            print("Available models:")
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                if line.strip():
                    model_name = line.split()[0]
                    print(f"  - {model_name}")
            return True
        else:
            print("⚠️  Ollama is installed but not running")
            return False
    except FileNotFoundError:
        print("❌ Ollama is not installed!")
        print("Please install Ollama from: https://ollama.ai/")
        return False

def setup_directories():
    """Create necessary directories."""
    directories = ["mcp_contexts", "logs", "chroma_db"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")

def setup_database():
    """Setup the ChromaDB database."""
    print("🗄️  Setting up database...")
    try:
        subprocess.run([sys.executable, "setup_database.py"])
        print("✅ Database setup completed")
    except Exception as e:
        print(f"⚠️  Database setup issue: {e}")
        print("You can run setup manually with: python setup_database.py")

def run_api_server():
    """Run the FastAPI server."""
    print("🚀 Starting API server...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n🛑 API server stopped")

def run_web_interface():
    """Run the Streamlit web interface."""
    print("🌐 Starting web interface...")
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "pages/assistant.py", "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\n🛑 Web interface stopped")

def run_test():
    """Run the MCP test."""
    print("🧪 Running MCP test...")
    try:
        subprocess.run([sys.executable, "test_mcp.py"])
    except Exception as e:
        print(f"❌ Test failed: {e}")

def run_api_client_example():
    """Run the API client example."""
    print("📡 Running API client example...")
    try:
        subprocess.run([sys.executable, "mcp_api_client.py"])
    except Exception as e:
        print(f"❌ API client example failed: {e}")

def main():
    """Main function to coordinate the startup process."""
    print("🤖 Angel Stylus Coding Assistant with MCP Support")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Setup directories
    setup_directories()
    
    # Check if requirements file exists
    if not os.path.exists("requirements_mcp.txt"):
        print("❌ requirements_mcp.txt not found!")
        return
    
    # Install dependencies
    install_dependencies()
    
    # Setup database if needed
    setup_database()
    
    # Check Ollama
    ollama_ok = check_ollama()
    if not ollama_ok:
        print("\n⚠️  Ollama is required for the LLM functionality.")
        print("You can still test the MCP framework, but LLM responses won't work.")
    
    print("\n" + "=" * 60)
    print("🎯 What would you like to do?")
    print("1. Run API server (http://localhost:8001)")
    print("2. Run web interface (http://localhost:8501)")
    print("3. Run both API server and web interface")
    print("4. Test MCP functionality")
    print("5. Run API client example")
    print("6. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-6): ").strip()
            
            if choice == "1":
                run_api_server()
                break
            elif choice == "2":
                run_web_interface()
                break
            elif choice == "3":
                print("🚀 Starting both API server and web interface...")
                print("API server will run on http://localhost:8001")
                print("Web interface will run on http://localhost:8501")
                print("Press Ctrl+C to stop both services")
                
                # Start API server in a separate thread
                api_thread = threading.Thread(target=run_api_server, daemon=True)
                api_thread.start()
                
                # Wait a moment for API server to start
                time.sleep(3)
                
                # Start web interface in main thread
                run_web_interface()
                break
            elif choice == "4":
                run_test()
                break
            elif choice == "5":
                run_api_client_example()
                break
            elif choice == "6":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-6.")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main() 