"""
Memory Manager for the Mentorship AI Application.
Stores and retrieves long-term context about the user's business and past sessions.
"""

import json
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Default path for memory storage (relative to the livekit-agent directory)
DEFAULT_MEMORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "user_memory.json")


class MemoryManager:
    """
    Manages persistent memory for the mentorship application.
    Stores user context, business details, and conversation summaries.
    """

    def __init__(self, memory_path: Optional[str] = None):
        self.memory_path = memory_path or DEFAULT_MEMORY_PATH
        self._ensure_data_directory()
        self.memory = self._load_memory()

    def _ensure_data_directory(self):
        """Create the data directory if it doesn't exist."""
        data_dir = os.path.dirname(self.memory_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Created data directory: {data_dir}")

    def _load_memory(self) -> Dict[str, Any]:
        """Load memory from file or return empty structure."""
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded memory with {len(data.get('sessions', []))} past sessions")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load memory, starting fresh: {e}")
        
        return self._create_empty_memory()

    def _create_empty_memory(self) -> Dict[str, Any]:
        """Create the initial empty memory structure."""
        return {
            "user_profile": {
                "name": None,
                "business_name": None,
                "business_type": None,
                "team_size": None,
                "main_challenges": [],
            },
            "sessions": [],
            "goals": [],
            "key_insights": [],
            "last_updated": None
        }

    def save(self):
        """Persist memory to disk."""
        self.memory["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
            logger.info("Memory saved successfully")
        except IOError as e:
            logger.error(f"Failed to save memory: {e}")

    def update_user_profile(self, **kwargs):
        """Update user profile fields."""
        for key, value in kwargs.items():
            if key in self.memory["user_profile"]:
                self.memory["user_profile"][key] = value
        self.save()

    def add_session_summary(self, summary: str, topics: list = None):
        """Add a summary of the current session."""
        session = {
            "date": datetime.now().isoformat(),
            "summary": summary,
            "topics": topics or []
        }
        self.memory["sessions"].append(session)
        # Keep only last 10 sessions to avoid context overload
        if len(self.memory["sessions"]) > 10:
            self.memory["sessions"] = self.memory["sessions"][-10:]
        self.save()

    def add_goal(self, goal: str, deadline: str = None):
        """Track a business goal."""
        self.memory["goals"].append({
            "goal": goal,
            "deadline": deadline,
            "created": datetime.now().isoformat(),
            "completed": False
        })
        self.save()

    def add_insight(self, insight: str):
        """Store a key insight about the user's business."""
        self.memory["key_insights"].append({
            "insight": insight,
            "date": datetime.now().isoformat()
        })
        # Keep only last 20 insights
        if len(self.memory["key_insights"]) > 20:
            self.memory["key_insights"] = self.memory["key_insights"][-20:]
        self.save()

    def get_context_prompt(self) -> str:
        """
        Generate a context string to inject into the AI's system prompt.
        Returns a summary of what the AI should "remember" about the user.
        """
        profile = self.memory["user_profile"]
        sessions = self.memory["sessions"]
        goals = self.memory["goals"]
        insights = self.memory["key_insights"]

        context_parts = []

        # User Profile
        if profile.get("name") or profile.get("business_name"):
            profile_str = "## Sobre o Empresário:\n"
            if profile.get("name"):
                profile_str += f"- Nome: {profile['name']}\n"
            if profile.get("business_name"):
                profile_str += f"- Empresa: {profile['business_name']}\n"
            if profile.get("business_type"):
                profile_str += f"- Tipo de negócio: {profile['business_type']}\n"
            if profile.get("team_size"):
                profile_str += f"- Tamanho da equipe: {profile['team_size']}\n"
            if profile.get("main_challenges"):
                profile_str += f"- Desafios principais: {', '.join(profile['main_challenges'])}\n"
            context_parts.append(profile_str)

        # Recent Sessions
        if sessions:
            sessions_str = "## Sessões Anteriores:\n"
            for i, session in enumerate(sessions[-3:], 1):  # Last 3 sessions
                date = session.get("date", "")[:10]  # Just the date part
                sessions_str += f"- ({date}): {session.get('summary', 'No summary')}\n"
            context_parts.append(sessions_str)

        # Active Goals
        active_goals = [g for g in goals if not g.get("completed")]
        if active_goals:
            goals_str = "## Metas em Andamento:\n"
            for goal in active_goals[-5:]:
                deadline = f" (prazo: {goal.get('deadline')})" if goal.get("deadline") else ""
                goals_str += f"- {goal['goal']}{deadline}\n"
            context_parts.append(goals_str)

        # Key Insights
        if insights:
            insights_str = "## Insights Importantes sobre o Negócio:\n"
            for ins in insights[-5:]:
                insights_str += f"- {ins['insight']}\n"
            context_parts.append(insights_str)

        if context_parts:
            header = "\n\n---\n## CONTEXTO DO EMPRESÁRIO (Lembre-se destas informações):\n"
            return header + "\n".join(context_parts)
        
        return ""  # No context yet


# Singleton instance for easy access
_memory_instance: Optional[MemoryManager] = None

def get_memory_manager() -> MemoryManager:
    """Get or create the singleton MemoryManager instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryManager()
    return _memory_instance
