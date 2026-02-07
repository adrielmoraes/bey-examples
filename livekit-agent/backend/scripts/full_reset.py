import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database import engine
from sqlalchemy import text

def clean_and_recreate():
    print("Iniciando limpeza profunda do banco de dados...")
    tables_to_drop = [
        "messages", "reports", "sessions", "user_profiles", 
        "goals", "insights", "documents"
    ]
    
    with engine.connect() as conn:
        # Disable foreign key checks for the session if possible, 
        # but in Postgres we use CASCADE.
        for table in tables_to_drop:
            try:
                print(f"Removendo tabela {table} (CASCADE)...")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
            except Exception as e:
                print(f"Erro ao remover {table}: {e}")
        
        conn.commit()
        print("Limpeza concluída!")

    # Now recreate using models
    print("Recriando tabelas a partir dos modelos...")
    from backend.models import Base
    Base.metadata.create_all(bind=engine)
    print("Esquema recriado com sucesso!")

if __name__ == "__main__":
    clean_and_recreate()
