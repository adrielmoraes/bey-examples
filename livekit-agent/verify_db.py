import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.memory_manager import get_memory_manager
from backend.document_store import get_document_store

def verify():
    print("Iniciando verificação de banco de dados...")
    
    # 1. Test MemoryManager
    memory = get_memory_manager()
    print("MemoryManager inicializado.")
    
    print("Atualizando perfil do usuário...")
    memory.update_user_profile(name="Adriel", business_name="Consultoria Empresarial")
    
    print("Adicionando meta...")
    memory.add_goal("Migrar para banco de dados", "2026-02-07")
    
    print("Recuperando contexto...")
    context = memory.get_context_prompt()
    if "Consultoria Empresarial" in context and "Migrar para banco de dados" in context:
        print("✅ Contexto do MemoryManager recuperado com sucesso!")
    else:
        print("❌ Falha ao recuperar contexto do MemoryManager.")
        print(f"Contexto: {context}")

    # 2. Test DocumentStore
    docs = get_document_store()
    print("DocumentStore inicializado.")
    
    print("Adicionando documento...")
    docs.add_document("teste.txt", "Este é um conteúdo de teste para busca RAG.")
    
    print("Buscando documento...")
    results = docs.search("RAG")
    if results and any(r['filename'] == "teste.txt" for r in results):
        print("✅ Busca no DocumentStore funcionando corretamente!")
    else:
        print("❌ Falha na busca do DocumentStore.")
        print(f"Resultados: {results}")

    print("\nVerificação concluída!")

if __name__ == "__main__":
    verify()
