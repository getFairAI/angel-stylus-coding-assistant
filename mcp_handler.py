import json
import os
import time
from typing import Dict, List, Optional, Any
from logger import log_info

class MCPHandler:
    """
    Model Context Protocol (MCP) handler for maintaining conversation context
    across multiple interactions with the Angel Stylus Coding Assistant.
    """
    
    def __init__(self, context_file_path="./mcp_contexts"):
        """
        Initialize the MCP handler with the path to store context files.
        
        Args:
            context_file_path: Directory to store context files
        """
        self.context_file_path = context_file_path
        self.active_contexts = {}  # In-memory cache of active contexts
        
        # Ensure context directory exists
        if not os.path.exists(context_file_path):
            os.makedirs(context_file_path)
            
    def create_session(self, session_id: str, initial_data: Optional[Dict] = None) -> Dict:
        """
        Create a new MCP session with optional initial data.
        
        Args:
            session_id: Unique identifier for the session
            initial_data: Optional initial context data
            
        Returns:
            The created context
        """
        context = {
            "session_id": session_id,
            "created_at": time.time(),
            "last_updated": time.time(),
            "interactions": [],
            "metadata": initial_data or {}
        }
        
        # Save to disk and memory
        self._save_context(session_id, context)
        self.active_contexts[session_id] = context
        
        log_info(f"Created new MCP session: {session_id}")
        return context
    
    def add_interaction(self, session_id: str, user_prompt: str, system_response: str, 
                      retrieved_docs: Optional[List[str]] = None) -> Dict:
        """
        Add a new interaction to an existing session.
        
        Args:
            session_id: Session ID
            user_prompt: The user's input
            system_response: The system's response
            retrieved_docs: Optional list of retrieved document chunks
            
        Returns:
            Updated context
        """
        # Get or create context
        context = self.get_context(session_id)
        if not context:
            context = self.create_session(session_id)
        
        # Add the new interaction
        interaction = {
            "timestamp": time.time(),
            "user_prompt": user_prompt,
            "system_response": system_response,
            "retrieved_docs": retrieved_docs or []
        }
        
        context["interactions"].append(interaction)
        context["last_updated"] = time.time()
        
        # Save updated context
        self._save_context(session_id, context)
        
        return context
    
    def get_context(self, session_id: str) -> Optional[Dict]:
        """
        Retrieve the context for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Context data or None if not found
        """
        # Check in-memory cache first
        if session_id in self.active_contexts:
            return self.active_contexts[session_id]
        
        # Try to load from disk
        context_file = os.path.join(self.context_file_path, f"{session_id}.json")
        if os.path.exists(context_file):
            try:
                with open(context_file, 'r') as f:
                    context = json.load(f)
                    self.active_contexts[session_id] = context
                    return context
            except Exception as e:
                log_info(f"Error loading context for session {session_id}: {str(e)}")
        
        return None
    
    def get_conversation_history(self, session_id: str, max_interactions: int = 5) -> str:
        """
        Get formatted conversation history for a session, limited to the most recent interactions.
        
        Args:
            session_id: Session ID
            max_interactions: Maximum number of past interactions to include
            
        Returns:
            Formatted conversation history
        """
        context = self.get_context(session_id)
        if not context or not context.get("interactions"):
            return ""
        
        # Get the most recent interactions up to max_interactions
        recent_interactions = context["interactions"][-max_interactions:]
        
        # Format the conversation history
        history = []
        for interaction in recent_interactions:
            history.append(f"User: {interaction['user_prompt']}")
            history.append(f"Assistant: {interaction['system_response']}")
        
        return "\n\n".join(history)
    
    def _save_context(self, session_id: str, context: Dict) -> None:
        """
        Save context to disk.
        
        Args:
            session_id: Session ID
            context: Context data to save
        """
        context_file = os.path.join(self.context_file_path, f"{session_id}.json")
        try:
            with open(context_file, 'w') as f:
                json.dump(context, f, indent=2)
            
            # Update in-memory cache
            self.active_contexts[session_id] = context
        except Exception as e:
            log_info(f"Error saving context for session {session_id}: {str(e)}")
    
    def get_relevant_docs_from_history(self, session_id: str) -> List[str]:
        """
        Get a list of relevant document chunks from past interactions.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of relevant document chunks
        """
        context = self.get_context(session_id)
        if not context or not context.get("interactions"):
            return []
        
        # Collect unique document chunks from past interactions
        unique_docs = set()
        for interaction in context["interactions"]:
            if interaction.get("retrieved_docs"):
                for doc in interaction["retrieved_docs"]:
                    unique_docs.add(doc)
        
        return list(unique_docs) 