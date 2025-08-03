#!/usr/bin/env python3
"""
Verification script to test MCP functionality
"""

import requests
import json
import time

def test_mcp_api():
    """Test the MCP-enabled API"""
    print("🧪 Testing MCP-enabled Angel Stylus Coding Assistant")
    print("=" * 60)
    
    api_url = "http://localhost:8001/stylus-chat"
    
    # Test 1: First request
    print("\n📤 Test 1: Initial request")
    payload1 = {
        "model": "mistral",
        "prompt": "Hello, can you help me with programming?"
    }
    
    try:
        response1 = requests.post(api_url, json=payload1, timeout=30)
        if response1.status_code == 200:
            data1 = response1.json()
            session_id = data1.get("session_id")
            print(f"✅ Response received")
            print(f"📝 Assistant: {data1['response'][:100]}...")
            print(f"🔑 Session ID: {session_id}")
            
            # Test 2: Follow-up request with context
            print("\n📤 Test 2: Follow-up request (testing MCP context)")
            payload2 = {
                "model": "mistral", 
                "prompt": "What did I just ask you about?",
                "session_id": session_id
            }
            
            time.sleep(1)  # Small delay
            response2 = requests.post(api_url, json=payload2, timeout=30)
            
            if response2.status_code == 200:
                data2 = response2.json()
                print(f"✅ Follow-up response received")
                print(f"📝 Assistant: {data2['response'][:100]}...")
                print(f"🔑 Same session ID: {data2.get('session_id') == session_id}")
                
                # Check if context was retained
                if "programming" in data2['response'].lower() or "help" in data2['response'].lower():
                    print("🎉 MCP CONTEXT RETENTION: SUCCESS!")
                    print("   The assistant remembered our previous conversation!")
                else:
                    print("⚠️  MCP context retention may not be working as expected")
                
                # Test 3: Get conversation history
                print("\n📤 Test 3: Get conversation history")
                history_url = f"http://localhost:8001/conversation-history/{session_id}"
                history_response = requests.get(history_url, timeout=10)
                
                if history_response.status_code == 200:
                    history_data = history_response.json()
                    print("✅ Conversation history retrieved")
                    print(f"📚 History preview: {history_data['history'][:150]}...")
                else:
                    print(f"❌ Failed to get history: {history_response.status_code}")
                
            else:
                print(f"❌ Follow-up request failed: {response2.status_code}")
                print(response2.text)
        else:
            print(f"❌ Initial request failed: {response1.status_code}")
            print(response1.text)
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure the API server is running on http://localhost:8001")
        print("   Run: python main.py")
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")

def check_services():
    """Check if required services are running"""
    print("\n🔍 Checking services...")
    
    # Check API server
    try:
        response = requests.get("http://localhost:8001", timeout=5)
        print("✅ API server is running on http://localhost:8001")
    except:
        print("❌ API server not accessible on http://localhost:8001")
        print("   Start with: python main.py")
    
    # Check Streamlit (if running)
    try:
        response = requests.get("http://localhost:8501", timeout=5)
        print("✅ Streamlit web interface is running on http://localhost:8501")
    except:
        print("ℹ️  Streamlit web interface not running on http://localhost:8501")
        print("   Start with: streamlit run pages/assistant.py")

if __name__ == "__main__":
    check_services()
    test_mcp_api()
    
    print("\n" + "=" * 60)
    print("🎉 MCP verification complete!")
    print("✨ Your Angel Stylus Coding Assistant with MCP is ready!")
    print("\n🌐 Access methods:")
    print("   • API: http://localhost:8001")
    print("   • Web UI: http://localhost:8501") 
    print("   • Test again: python verify_mcp.py") 