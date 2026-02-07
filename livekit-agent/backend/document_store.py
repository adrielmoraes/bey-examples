"""
Document Store for the Mentorship AI Application.
Handles document ingestion and search using the SQL database for persistence.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session as SQLAlchemySession
from .database import SessionLocal
from .models import Document, UserProfile

logger = logging.getLogger(__name__)

class DocumentStore:
    """
    Manages business documents in the database.
    Provides simple text search across persisted document content.
    """

    def __init__(self, db: Optional[SQLAlchemySession] = None):
        self._provided_db = db
        self._ensure_user_context()

    def _get_db(self):
        if self._provided_db:
            return self._provided_db
        return SessionLocal()

    def _close_db(self, db):
        if not self._provided_db:
            db.close()

    def _ensure_user_context(self):
        """Find or create the default user for document assignment."""
        db = self._get_db()
        try:
            user = db.query(UserProfile).first()
            if not user:
                user = UserProfile(name="Empresário")
                db.add(user)
                db.commit()
            self.user_id = user.id
        finally:
            self._close_db(db)

    def add_document(self, filename: str, content: str):
        """Add or update a document in the database."""
        db = self._get_db()
        try:
            existing = db.query(Document).filter_by(filename=filename).first()
            if existing:
                existing.content = content
            else:
                new_doc = Document(
                    user_id=self.user_id,
                    filename=filename,
                    content=content
                )
                db.add(new_doc)
            db.commit()
            logger.info(f"Persisted document: {filename}")
        except Exception as e:
            logger.error(f"Failed to save document {filename}: {e}")
            db.rollback()
        finally:
            self._close_db(db)

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Keyword search across documents in the database.
        """
        db = self._get_db()
        results = []
        try:
            query_lower = query.lower()
            query_terms = query_lower.split()
            
            # For MVP, we fetch all and search in memory. 
            # In production, use database full-text search (TSVector/GIN).
            docs = db.query(Document).all()
            
            for doc in docs:
                content_lower = doc.content.lower()
                matches = [term for term in query_terms if term in content_lower]
                if not matches:
                    continue

                snippet = self._find_snippet(doc.content, query_terms)
                score = len(matches) / len(query_terms)

                results.append({
                    "filename": doc.filename,
                    "snippet": snippet,
                    "score": score
                })

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:max_results]
        finally:
            self._close_db(db)

    def _find_snippet(self, content: str, query_terms: List[str], snippet_length: int = 500) -> str:
        """Find relevant snippet in content."""
        content_lower = content.lower()
        best_pos = len(content)
        for term in query_terms:
            pos = content_lower.find(term)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        if best_pos == len(content):
            return content[:snippet_length] + "..."

        start = max(0, best_pos - 100)
        end = min(len(content), best_pos + snippet_length - 100)
        snippet = content[start:end]
        if start > 0: snippet = "..." + snippet
        if end < len(content): snippet = snippet + "..."
        return snippet

    def get_context_for_query(self, query: str) -> str:
        """Get relevant context for AI."""
        results = self.search(query)
        if not results:
            return ""

        context_parts = ["## Informações dos Documentos do Empresário:"]
        for result in results:
            context_parts.append(f"\n### De: {result['filename']}")
            context_parts.append(result['snippet'])

        return "\n".join(context_parts)

    def get_all_documents_summary(self) -> str:
        """Get summary of all available documents."""
        db = self._get_db()
        try:
            docs = db.query(Document).all()
            if not docs:
                return ""
            
            summary = "## Documentos Disponíveis do Empresário:\n"
            for doc in docs:
                word_count = len(doc.content.split())
                summary += f"- {doc.filename} ({word_count} palavras)\n"
            return summary
        finally:
            self._close_db(db)

    def list_documents(self) -> List[str]:
        """List all document filenames."""
        db = self._get_db()
        try:
            return [doc.filename for doc in db.query(Document).all()]
        finally:
            self._close_db(db)

# Singleton instance
_store_instance: Optional[DocumentStore] = None

def get_document_store() -> DocumentStore:
    """Get or create the singleton DocumentStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = DocumentStore()
    return _store_instance
