
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
from google.genai import types  # For AudioTranscriptionConfig
import backend.gemini_agent

load_dotenv() # Load at top level to ensure all processes have access

logger = logging.getLogger(__name__)

async def entrypoint(ctx: JobContext) -> None:
    # Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Handle different env var names for the API Key
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY or GOOGLE_GEMINI_API_KEY not found in environment")
    
    # Beyond Presence API Key mapping
    if "BEY_API_KEY" not in os.environ and "BEYOND_PRESENCE_API_KEY" in os.environ:
        os.environ["BEY_API_KEY"] = os.environ["BEYOND_PRESENCE_API_KEY"]

    # Initialize Gemini Realtime Model
    model = realtime.RealtimeModel(
        instructions="Você é um assistente de IA futurista e prestativo. Seu nome é Cosmo. Responda sempre em Português.",
        voice="Puck",
        temperature=0.8,
        api_key=api_key,
        # Use default modalities (AUDIO) - strings don't work, need types.Modality enum
        # modalities=[types.Modality.AUDIO] is the default, so we can omit it
        input_audio_transcription=types.AudioTranscriptionConfig(),  # Enable transcription
    )

    # Initialize and start our custom agent
    # This handles the 2-way audio between Room and Gemini
    agent = backend.gemini_agent.GeminiMultimodalAgent(model=model)
    # Initialize Beyond Presence Avatar Session
    bey_avatar_session = bey.AvatarSession(avatar_id=os.environ.get("BEY_AVATAR_ID"))

    # Start both services concurrently to reduce latency
    logger.info("Starting Gemini Agent and Avatar Session concurrently...")
    try:
        await asyncio.gather(
            agent.start(ctx.room),
            bey_avatar_session.start(agent, room=ctx.room)
        )
        logger.info("Both services started successfully")
    except Exception as e:
        logger.error(f"Failed to start services: {e}")
        logger.info("Beyond Presence Avatar Session started")
    except Exception as e:
        logger.error(f"Failed to start Avatar Session: {e}")

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
