
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

    # Load memory context
    memory = get_memory_manager()
    memory_context = memory.get_context_prompt()

    # Host Agent (Cosmo) prompt with specialist invocation capabilities
    specialists_list = "\n".join([f"- {name}: {role}" for name, role in list_specialists().items()])
    
    mentoria_prompt = f"""
Você é **Cosmo**, o mentor empresarial líder de uma equipe de especialistas. Sua missão é guiar empreendedores no crescimento de seus negócios.

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

    model = realtime.RealtimeModel(
        instructions=mentoria_prompt,
        voice="Puck",
        temperature=0.8,
        api_key=api_key,
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )

    # Initialize the Host Agent (Cosmo)
    agent = backend.gemini_agent.GeminiMultimodalAgent(model=model)
    
    # Initialize Cosmo's Avatar
    host_avatar_id = os.environ.get("BEY_AVATAR_ID_HOST") or os.environ.get("BEY_AVATAR_ID")
    bey_avatar_session = bey.AvatarSession(avatar_id=host_avatar_id)

    # Initialize the Multi-Agent Orchestrator
    orchestrator = MultiAgentOrchestrator(
        host_agent=agent,
        room=ctx.room,
        api_key=api_key
    )

    # Store orchestrator reference in agent for potential use
    agent.orchestrator = orchestrator

    logger.info("Starting Cosmo (Host Agent) and Avatar Session...")
    try:
        await asyncio.gather(
            agent.start(ctx.room),
            bey_avatar_session.start(agent, room=ctx.room),
            orchestrator.start_all_specialists()
        )
        logger.info("Host Agent and Avatar started successfully")
        
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
