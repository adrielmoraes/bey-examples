# Mentoria Empresarial Inteligente - Multi-Agente 🚀

Bem-vindo ao sistema de **Mentoria Empresarial Multi-Agente**, uma plataforma de ponta que utiliza inteligência artificial multimodal (Gemini 2.0) e avatares digitais realistas (Beyond Presence) para guiar empreendedores.

O sistema simula uma sala de reunião real com um mentor principal e uma equipe de quatro especialistas, todos prontos para interagir simultaneamente.

---

## 🤖 A Equipe de Mentores

O sistema é composto por 5 agentes independentes, cada um com sua própria personalidade, voz e expertise:

### 🎙️ Cosmo (Host & Mentor Principal)
O cérebro central da conversa. Cosmo coordena a reunião, faz o diagnóstico estratégico e decide quando consultar os especialistas.
- **Voz:** Puck
- **Foco:** Estratégia, Gestão e Liderança.

### 📈 Maya (Especialista em Marketing)
Especialista em Growth Hacking e tráfego pago.
- **Avatar:** Feminino, enérgico.
- **Foco:** Funis de vendas, anúncios e redes sociais.

### 💰 Ricardo (Especialista Financeiro)
Analítico e metódico, focado na saúde financeira do negócio.
- **Avatar:** Masculino, analítico.
- **Foco:** Fluxo de caixa, precificação e investimentos.

### 💡 Lucas (Especialista em Produto)
Focado em inovação, tecnologia e metodologias ágeis.
- **Avatar:** Masculino, entusiasta.
- **Foco:** MVPs, UX e Roadmap tecnológico.

### ⚖️ Fernanda (Especialista Jurídico)
Segurança e conformidade para a jornada empreendedora.
- **Avatar:** Feminino, firme e cauteloso.
- **Foco:** Contratos, marcas e LGPD.

---

## 🛠️ Arquitetura Técnica

### 1. Inteligência & Áudio
- **Gemini 2.0 Flash Multimodal**: Utilizado como o motor de pensamento de todos os agentes.
- **LiveKit Agents SDK**: Orquestração de áudio e vídeo em tempo real.
- **Beyond Presence Plugin**: Geração de avatares sincronizados com os lábios (Lip-Sync).

### 2. Persistência de Dados (SQL)
O sistema migrou de arquivos JSON locais para um banco de dados **PostgreSQL (Neon)** usando **SQLAlchemy**, garantindo escalabilidade e robustez.
- **User Profiles**: Mantém o contexto contínuo do empresário e seus desafios.
- **Session History**: Logs de todas as mentorias para acompanhamento.
- **Goal Tracker**: Gestão de metas definidas durante a conversa.
- **RAG Knowledge Base**: Documentos PDF/TXT são armazenados em tabelas para busca semântica via DocumentStore.

### 3. Comunicação Multi-Agente
Diferente de sistemas convencionais, nossa arquitetura permite:
- **Inicialização Paralela**: Todos os 5 avatares entram na sala simultaneamente usando `asyncio.gather`.
- **Roteamento de Áudio Cruzado**: O Host pode "ouvir" e responder aos especialistas, criando uma dinâmica de debate real.
- **Independência de Identidade**: Cada agente possui seu próprio `participant_identity` no LiveKit.

---

## 🚀 Como Executar

### Pré-requisitos
- Python 3.10+
- Ambiente Virtual configurado
- Variáveis de ambiente no `.env` (LiveKit, Google Gemini, Beyond Presence e Database URL)

### Passos
1. **Instalar dependências**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Inicializar o Banco de Dados** (Primeira vez):
   ```bash
   python backend/scripts/migrate_json_to_db.py
   ```

3. **Iniciar o Backend**:
   ```bash
   python main.py dev
   ```

4. **Iniciar o Frontend**:
   ```bash
   python frontend/server.py
   ```

---

## 📂 Estrutura do Projeto
- `/backend`: Lógica dos agentes, modelos de dados e orquestração.
- `/frontend`: Interface web para visualização dos avatares.
- `/data`: Armazenamento histórico e backups.
- `verify_db.py`: Script de teste para garantir integridade do banco.
