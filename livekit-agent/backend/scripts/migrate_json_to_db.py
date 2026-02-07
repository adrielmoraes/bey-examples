import json
import os
import sys
from datetime import datetime

# Add the project root to path so we can import backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database import SessionLocal, engine, Base
from backend.models import UserProfile, Session, Goal, Insight, Document

def migrate():
    # Create tables if they don't exist
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    
    # Path to original JSON and documents
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    json_path = os.path.join(base_dir, "data", "user_memory.json")
    docs_path = os.path.join(base_dir, "data", "documents")

    try:
        # Check if we already have a profile
        existing_profile = db.query(UserProfile).first()
        if existing_profile:
            print("Database already has data. Skipping migration to avoid duplicates.")
            return

        # 1. Migrate user_memory.json
        if os.path.exists(json_path):
            print(f"Loading memory from {json_path}...")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Create UserProfile
            profile_data = data.get("user_profile", {})
            user = UserProfile(
                name=profile_data.get("name"),
                business_name=profile_data.get("business_name"),
                business_type=profile_data.get("business_type"),
                team_size=profile_data.get("team_size"),
                main_challenges=profile_data.get("main_challenges", [])
            )
            db.add(user)
            db.flush() # Get user.id

            # Sessions
            for s in data.get("sessions", []):
                try:
                    date_dt = datetime.fromisoformat(s.get("date"))
                except (ValueError, TypeError):
                    date_dt = datetime.utcnow()
                
                new_session = Session(
                    user_id=user.id,
                    date=date_dt,
                    summary=s.get("summary", ""),
                    topics=s.get("topics", [])
                )
                db.add(new_session)

            # Goals
            for g in data.get("goals", []):
                new_goal = Goal(
                    user_id=user.id,
                    goal=g.get("goal", ""),
                    deadline=g.get("deadline"),
                    completed=g.get("completed", False)
                )
                db.add(new_goal)

            # Insights
            for i in data.get("key_insights", []):
                try:
                    date_dt = datetime.fromisoformat(i.get("date"))
                except (ValueError, TypeError):
                    date_dt = datetime.utcnow()
                
                new_insight = Insight(
                    user_id=user.id,
                    insight=i.get("insight", ""),
                    date=date_dt
                )
                db.add(new_insight)

            print("User memory migrated.")
        else:
            print("No user_memory.json found.")
            # Create a default user if none exists
            user = UserProfile(name="Empresário")
            db.add(user)
            db.flush()

        # 2. Migrate Documents
        if os.path.exists(docs_path):
            print(f"Migrating documents from {docs_path}...")
            for filename in os.listdir(docs_path):
                filepath = os.path.join(docs_path, filename)
                if os.path.isfile(filepath):
                    ext = os.path.splitext(filename)[1].lower()
                    content = None
                    
                    if ext == ".txt":
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()
                        except Exception as e:
                            print(f"Error reading {filename}: {e}")
                    elif ext == ".pdf":
                        # We use the existing extraction logic if possible, or just skip PDF content migration
                        # for now and let the new DocumentStore handle it (or re-upload).
                        # For now, let's try to extract if pymupdf is available.
                        try:
                            import fitz
                            with fitz.open(filepath) as doc:
                                text_parts = [page.get_text() for page in doc]
                                content = "\n".join(text_parts)
                        except ImportError:
                            print(f"PyMuPDF not available, skipping content for {filename}. Can be re-indexed later.")
                        except Exception as e:
                            print(f"Error extracting PDF {filename}: {e}")

                    if content:
                        doc_obj = Document(
                            user_id=user.id,
                            filename=filename,
                            content=content
                        )
                        db.add(doc_obj)
            print("Documents migrated.")

        db.commit()
        print("Migration completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
