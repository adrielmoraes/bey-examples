# Consultoria Empresarial - Gemini Multimodal Live Agent

Este projeto implementa um **Agente de IA Multimodal** interativo com avatar 3D realista, capaz de conduzir conversas em tempo real (áudio e vídeo) utilizando a tecnologia Google Gemini e LiveKit.

## 🚀 Funcionalidades

- **Avatar 3D Realista**: Integração com *Beyond Presence* para um avatar com *lip-sync* preciso.
- **Inteligência Multimodal**: Usa o modelo **Gemini Realtime (Google)** para conversação fluida e natural.
- **Latência Otimizada**: Inicialização paralela de serviços para resposta rápida.
- **Interface Futurista**: Frontend responsivo com tema "Dark Purple & Lime Green".
- **Visualizador de Áudio**: Animação em tempo real que reage à voz do usuário.

## 🛠️ Tecnologias

- **Backend**: Python 3.12+, LiveKit Agents, Flask.
- **AI Engine**: Google Gemini Multimodal Live API via `livekit-plugins-google`.
- **Avatar**: LiveKit Plugin for Beyond Presence.
- **Frontend**: Vanilla JavaScript, HTML5, CSS3, LiveKit Client SDK.

## 📋 Pré-requisitos

- Python 3.12 ou superior
- Conta no [LiveKit Cloud](https://cloud.livekit.io/)
- Chaves de API:
  - LiveKit (URL, API Key, API Secret)
  - Google Gemini (API Key)
  - Beyond Presence (API Key)

## ⚙️ Configuração

1. **Clone o repositório**
   ```bash
   git clone https://github.com/adrielmoraes/Consultoria-Empresarial.git
   cd Consultoria-Empresarial
   ```

2. **Crie o ambiente virtual (recomendado)**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as variáveis de ambiente**
   Crie um arquivo `.env` na raiz (use `.env.template` como base):
   ```ini
   LIVEKIT_URL=wss://seu-projeto.livekit.cloud
   LIVEKIT_API_KEY=sua_key
   LIVEKIT_API_SECRET=seu_secret
   
   GOOGLE_API_KEY=sua_google_key
   BEYOND_PRESENCE_API_KEY=sua_bey_key
   BEY_AVATAR_ID=seu_avatar_id
   ```

## ▶️ Como Rodar

Para iniciar o sistema completo (Backend + Frontend):

### Opção 1: Script Automático (Windows)
Execute o arquivo batch:
```cmd
start_app.bat
```

### Opção 2: Manualmente
1. **Inicie o Frontend (Porta 8000)**
   ```bash
   python frontend/server.py
   ```
2. **Inicie o Backend (Agente)**
   ```bash
   python main.py dev
   ```
3. Acesse `http://localhost:8000` no navegador.

## 🐛 Solução de Problemas Comuns

- **Erro de Conexão**: Verifique se não há instâncias antigas do python rodando (`taskkill /F /IM python.exe` se necessário).
- **Sem Áudio**: Permita o acesso ao microfone no navegador.
- **Avatar não carrega**: Verifique a `BEYOND_PRESENCE_API_KEY` e logs do backend.

## 📄 Licença

Este projeto é privado e destinado a uso de consultoria empresarial.
