
import logging
import os
import sys
import asyncio

from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    WorkerType,
    cli,
)
from livekit.plugins import bey, google
from livekit.plugins.google import realtime
from google.genai import types
import backend.gemini_agent
from backend.memory_manager import get_memory_manager
from backend.multi_agent_orchestrator import MultiAgentOrchestrator
from backend.specialist_config import list_specialists

load_dotenv()

logger = logging.getLogger(__name__)


async def entrypoint(ctx: JobContext) -> None:
    """Main entrypoint for the mentorship agent."""
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # API Key handling
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY or GOOGLE_GEMINI_API_KEY not found in environment")
        return

    if "BEY_API_KEY" not in os.environ and "BEYOND_PRESENCE_API_KEY" in os.environ:
        os.environ["BEY_API_KEY"] = os.environ["BEYOND_PRESENCE_API_KEY"]

    bey_api_key_1 = os.environ.get("BEYOND_PRESENCE_API_KEY")
    bey_api_key_2 = os.environ.get("BEYOND_PRESENCE_API_KEY_2")

    if not bey_api_key_1:
         logger.warning("BEYOND_PRESENCE_API_KEY not found. Avatars may fail to load.")


    # Load memory context
    memory = get_memory_manager()
    memory_context = memory.get_context_prompt()

    host_name = os.environ.get("BEY_NAME_HOST", "Cosmo")
    specialists_list = "\n".join([f"- {name}: {role}" for name, role in list_specialists().items()])
    
    mentoria_prompt = f"""
Você é **{host_name}**, o mentor empresarial líder de uma equipe de especialistas. Sua missão é guiar empreendedores no crescimento de seus negócios.

## Sua Equipe de Especialistas:
Você pode chamar especialistas para ajudar quando o assunto for muito específico:
{specialists_list}

Para chamar um especialista, diga algo como: "Deixa eu chamar nossa especialista em marketing para te ajudar com isso."

## Sua Personalidade:
- Profissional, mas acessível e empático
- Direto ao ponto, sem rodeios
- Faz perguntas estratégicas para entender o contexto
- Coordena a equipe quando necessário

## Suas Especialidades Gerais:
1. **Gestão Financeira**: Fluxo de caixa, precificação, margem de lucro
2. **Estratégia de Negócios**: Posicionamento, diferenciação, análise de mercado
3. **Liderança e Equipe**: Contratação, delegação, cultura organizacional
4. **Vendas e Marketing**: Funil de vendas, captação de clientes
5. **Produtividade**: Gestão de tempo, processos, automação

## Estrutura da Conversa:
1. Cumprimente brevemente e pergunte qual é o principal desafio
2. Faça 2-3 perguntas de diagnóstico
3. Ofereça insights ou chame um especialista se o tema for muito específico
4. Confirme se o conselho foi útil

## Regras:
- Responda SEMPRE em Português Brasileiro
- Seja conciso (máximo 3-4 frases por resposta)
- Se precisar de um especialista, avise o empresário antes de chamá-lo
- Quando um especialista estiver na sala, coordene a conversa

## Memória:
- Lembre-se do nome do empresário e da empresa
- Anote metas e desafios para acompanhar o progresso
{memory_context}
"""

    # Explicitly set environment variables for plugins
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        os.environ["GOOGLE_GEMINI_API_KEY"] = api_key

    model = realtime.RealtimeModel(
        instructions=mentoria_prompt,
        model="gemini-2.0-flash-exp",
        voice="Puck",
        temperature=0.8,
        api_key=api_key,
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )


    # Initialize the Host Agent (Cosmo)
    agent = backend.gemini_agent.GeminiMultimodalAgent(model=model)
    
    # Initialize Cosmo's Avatar
    host_avatar_id = os.environ.get("BEY_AVATAR_ID_HOST") or os.environ.get("BEY_AVATAR_ID")
    bey_avatar_session = bey.AvatarSession(
        avatar_id=host_avatar_id,
        api_key=bey_api_key_1,
        avatar_participant_identity="cosmo",
        avatar_participant_name=host_name
    )



    # Redacted log to verify key existence (do not show full key)
    if api_key:
        logger.info(f"Gemini API Key loaded: {api_key[:4]}...{api_key[-4:]}")
    else:
        logger.error("Gemini API Key is MISSING!")

    # Initialize the Multi-Agent Orchestrator
    orchestrator = MultiAgentOrchestrator(
        host_agent=agent,
        room=ctx.room,
        google_api_key=api_key,
        api_key_1=bey_api_key_1,
        api_key_2=bey_api_key_2
    )


    # Store orchestrator reference in agent for potential use
    agent.orchestrator = orchestrator

    logger.info("Starting Cosmo (Host Agent) and Avatar Session...")
    try:
        # 1. Start Host Agent (Gemini)
        await agent.start(ctx.room)
        await asyncio.sleep(3.0)
        
        # 2. Start Host Avatar (Bey)
        await bey_avatar_session.start(agent, room=ctx.room)
        logger.info("Host Avatar started successfully")
        await asyncio.sleep(5.0) # Delay before starting specialists to avoid burst
        
        # 3. Start Specialists (Staggered inside with 5s delays)
        await orchestrator.start_all_specialists()
        
        logger.info("Host Agent and all services started successfully")


        
        # Log available specialists
        logger.info(f"Available specialists: {list(list_specialists().keys())}")
        
    except Exception as e:
        logger.error(f"Failed to start services: {e}")
        raise


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    # Force dev mode for local testing
    sys.argv = [sys.argv[0], "dev"]

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            worker_type=WorkerType.ROOM,
        )
    )
