"""
Document Store for the Mentorship AI Application.
Handles PDF/text file ingestion and simple text search for RAG-like context retrieval.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Default path for document storage
DEFAULT_DOCUMENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "documents")


class DocumentStore:
    """
    Manages business documents uploaded by the user.
    Provides simple text extraction and search capabilities.
    """

    def __init__(self, documents_path: Optional[str] = None):
        self.documents_path = documents_path or DEFAULT_DOCUMENTS_PATH
        self._ensure_directory()
        self.documents: Dict[str, str] = {}  # filename -> content
        self._load_existing_documents()

    def _ensure_directory(self):
        """Create the documents directory if it doesn't exist."""
        if not os.path.exists(self.documents_path):
            os.makedirs(self.documents_path)
            logger.info(f"Created documents directory: {self.documents_path}")

    def _load_existing_documents(self):
        """Load all existing text documents from the directory."""
        for filename in os.listdir(self.documents_path):
            filepath = os.path.join(self.documents_path, filename)
            if os.path.isfile(filepath):
                self._load_document(filepath)
        logger.info(f"Loaded {len(self.documents)} documents")

    def _load_document(self, filepath: str):
        """Load a single document into memory."""
        filename = os.path.basename(filepath)
        ext = Path(filepath).suffix.lower()

        try:
            if ext == ".txt":
                with open(filepath, "r", encoding="utf-8") as f:
                    self.documents[filename] = f.read()
            elif ext == ".pdf":
                content = self._extract_pdf_text(filepath)
                if content:
                    self.documents[filename] = content
            else:
                logger.debug(f"Skipping unsupported file type: {filename}")
        except Exception as e:
            logger.error(f"Failed to load document {filename}: {e}")

    def _extract_pdf_text(self, filepath: str) -> Optional[str]:
        """
        Extract text from a PDF file.
        Uses PyMuPDF (fitz) if available, otherwise returns None.
        """
        try:
            import fitz  # PyMuPDF
            text_parts = []
            with fitz.open(filepath) as doc:
                for page in doc:
                    text_parts.append(page.get_text())
            return "\n".join(text_parts)
        except ImportError:
            logger.warning("PyMuPDF not installed. Install with: pip install pymupdf")
            return None
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return None

    def add_document(self, filename: str, content: str):
        """Add a document directly from text content."""
        self.documents[filename] = content
        # Also save to disk
        filepath = os.path.join(self.documents_path, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Saved document: {filename}")
        except IOError as e:
            logger.error(f"Failed to save document: {e}")

    def save_uploaded_file(self, file_bytes: bytes, filename: str) -> bool:
        """Save an uploaded file and load it into memory."""
        filepath = os.path.join(self.documents_path, filename)
        try:
            with open(filepath, "wb") as f:
                f.write(file_bytes)
            self._load_document(filepath)
            logger.info(f"Uploaded and loaded: {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            return False

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Simple keyword search across all documents.
        Returns the most relevant snippets containing the query terms.
        """
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()

        for filename, content in self.documents.items():
            content_lower = content.lower()
            
            # Check if any query term exists in the document
            matches = [term for term in query_terms if term in content_lower]
            if not matches:
                continue

            # Find the best matching snippet
            snippet = self._find_snippet(content, query_terms)
            score = len(matches) / len(query_terms)  # Simple relevance score

            results.append({
                "filename": filename,
                "snippet": snippet,
                "score": score
            })

        # Sort by score and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def _find_snippet(self, content: str, query_terms: List[str], snippet_length: int = 500) -> str:
        """Find the most relevant snippet containing query terms."""
        content_lower = content.lower()
        
        # Find the first occurrence of any query term
        best_pos = len(content)
        for term in query_terms:
            pos = content_lower.find(term)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        if best_pos == len(content):
            return content[:snippet_length] + "..."

        # Extract snippet around the match
        start = max(0, best_pos - 100)
        end = min(len(content), best_pos + snippet_length - 100)
        snippet = content[start:end]

        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    def get_context_for_query(self, query: str) -> str:
        """
        Get document context relevant to a query.
        Returns a formatted string to inject into the AI context.
        """
        results = self.search(query)
        if not results:
            return ""

        context_parts = ["## Informações dos Documentos do Empresário:"]
        for result in results:
            context_parts.append(f"\n### De: {result['filename']}")
            context_parts.append(result['snippet'])

        return "\n".join(context_parts)

    def get_all_documents_summary(self) -> str:
        """Get a summary of all available documents."""
        if not self.documents:
            return ""
        
        summary = "## Documentos Disponíveis do Empresário:\n"
        for filename, content in self.documents.items():
            word_count = len(content.split())
            summary += f"- {filename} ({word_count} palavras)\n"
        return summary

    def list_documents(self) -> List[str]:
        """List all loaded document filenames."""
        return list(self.documents.keys())


# Singleton instance
_store_instance: Optional[DocumentStore] = None

def get_document_store() -> DocumentStore:
    """Get or create the singleton DocumentStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = DocumentStore()
    return _store_instance
