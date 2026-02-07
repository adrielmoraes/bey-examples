"""
Memory Manager for the Mentorship AI Application.
Stores and retrieves long-term context using a SQL database.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session as SQLAlchemySession
from .database import SessionLocal
from .models import UserProfile, Session, Goal, Insight

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Manages persistent memory for the mentorship application.
    Stores user context, business details, and conversation summaries in the database.
    """

    def __init__(self, db: Optional[SQLAlchemySession] = None):
        # We'll use a session for each operation or use the provided one
        self._provided_db = db
        self._ensure_user_exists()

    def _get_db(self):
        if self._provided_db:
            return self._provided_db
        return SessionLocal()

    def _close_db(self, db):
        if not self._provided_db:
            db.close()

    def _ensure_user_exists(self):
        """Ensure at least one user exists in the database."""
        db = self._get_db()
        try:
            user = db.query(UserProfile).first()
            if not user:
                user = UserProfile(name="Empresário")
                db.add(user)
                db.commit()
                logger.info("Created default user profile in database")
            self.user_id = user.id
        finally:
            self._close_db(db)

    def get_user_profile(self) -> Dict[str, Any]:
        """Fetch the current user profile."""
        db = self._get_db()
        try:
            user = db.query(UserProfile).get(self.user_id)
            return {
                "name": user.name,
                "business_name": user.business_name,
                "business_type": user.business_type,
                "team_size": user.team_size,
                "main_challenges": user.main_challenges or [],
            }
        finally:
            self._close_db(db)

    def update_user_profile(self, **kwargs):
        """Update user profile fields in the database."""
        db = self._get_db()
        try:
            user = db.query(UserProfile).get(self.user_id)
            if user:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                user.last_updated = datetime.utcnow()
                db.commit()
                logger.info(f"Updated user profile for user {self.user_id}")
        finally:
            self._close_db(db)

    def add_session_summary(self, summary: str, topics: List[str] = None):
        """Add a session summary to the database."""
        db = self._get_db()
        try:
            new_session = Session(
                user_id=self.user_id,
                summary=summary,
                topics=topics or [],
                date=datetime.utcnow()
            )
            db.add(new_session)
            db.commit()
            logger.info(f"Added session summary for user {self.user_id}")
        finally:
            self._close_db(db)

    def add_goal(self, goal_text: str, deadline: str = None):
        """Track a business goal in the database."""
        db = self._get_db()
        try:
            new_goal = Goal(
                user_id=self.user_id,
                goal=goal_text,
                deadline=deadline,
                created_at=datetime.utcnow(),
                completed=False
            )
            db.add(new_goal)
            db.commit()
            logger.info(f"Added goal for user {self.user_id}")
        finally:
            self._close_db(db)

    def add_insight(self, insight_text: str):
        """Store a key insight in the database."""
        db = self._get_db()
        try:
            new_insight = Insight(
                user_id=self.user_id,
                insight=insight_text,
                date=datetime.utcnow()
            )
            db.add(new_insight)
            db.commit()
            logger.info(f"Added insight for user {self.user_id}")
        finally:
            self._close_db(db)

    def get_context_prompt(self) -> str:
        """
        Generate a context string to inject into the AI's system prompt from the database.
        """
        db = self._get_db()
        try:
            user = db.query(UserProfile).get(self.user_id)
            sessions = db.query(Session).filter_by(user_id=self.user_id).order_by(Session.date.desc()).limit(3).all()
            goals = db.query(Goal).filter_by(user_id=self.user_id, completed=False).limit(5).all()
            insights = db.query(Insight).filter_by(user_id=self.user_id).order_by(Insight.date.desc()).limit(5).all()

            context_parts = []

            # User Profile
            profile_str = "## Sobre o Empresário:\n"
            profile_str += f"- Nome: {user.name or 'Não informado'}\n"
            if user.business_name:
                profile_str += f"- Empresa: {user.business_name}\n"
            if user.business_type:
                profile_str += f"- Tipo de negócio: {user.business_type}\n"
            if user.team_size:
                profile_str += f"- Tamanho da equipe: {user.team_size}\n"
            if user.main_challenges:
                profile_str += f"- Desafios principais: {', '.join(user.main_challenges)}\n"
            context_parts.append(profile_str)

            # Recent Sessions
            if sessions:
                sessions_str = "## Sessões Anteriores:\n"
                for sess in sessions:
                    date_str = sess.date.strftime("%Y-%m-%d")
                    sessions_str += f"- ({date_str}): {sess.summary}\n"
                context_parts.append(sessions_str)

            # Active Goals
            if goals:
                goals_str = "## Metas em Andamento:\n"
                for g in goals:
                    deadline_str = f" (prazo: {g.deadline})" if g.deadline else ""
                    goals_str += f"- {g.goal}{deadline_str}\n"
                context_parts.append(goals_str)

            # Key Insights
            if insights:
                insights_str = "## Insights Importantes sobre o Negócio:\n"
                for ins in insights:
                    insights_str += f"- {ins.insight}\n"
                context_parts.append(insights_str)

            if context_parts:
                header = "\n\n---\n## CONTEXTO DO EMPRESÁRIO (Lembre-se destas informações):\n"
                return header + "\n".join(context_parts)
            
            return ""
        finally:
            self._close_db(db)

# Singleton instance for easy access
_memory_instance: Optional[MemoryManager] = None

def get_memory_manager() -> MemoryManager:
    """Get or create the singleton MemoryManager instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryManager()
    return _memory_instance
