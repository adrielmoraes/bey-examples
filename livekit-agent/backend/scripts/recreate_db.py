import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database import engine, Base
from backend.models import UserProfile, Session, Goal, Insight, Document

def recreate():
    print("Dropando todas as tabelas...")
    Base.metadata.drop_all(bind=engine)
    print("Recriando todas as tabelas...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas recriadas com sucesso!")

if __name__ == "__main__":
    recreate()
