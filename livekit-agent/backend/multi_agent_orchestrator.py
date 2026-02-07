"""
Multi-Agent Orchestrator for the Mentorship Application.
Manages the Host agent and spawns Specialist agents as needed.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any

from livekit import rtc
from livekit.agents import llm, utils
from livekit.plugins import bey, google
from livekit.plugins.google import realtime
from google.genai import types

from backend.specialist_config import SPECIALISTS, SpecialistConfig, get_specialist_for_topic
from backend.memory_manager import get_memory_manager

logger = logging.getLogger("multi-agent-orchestrator")


class SpecialistAgent:
    """
    A specialist agent that joins the room with its own avatar and expertise.
    """

    def __init__(self, config: SpecialistConfig, bey_api_key: str, google_api_key: str):
        self.config = config
        self.bey_api_key = bey_api_key
        self.google_api_key = google_api_key
        
        # Log redacted keys for verification
        bey_short = f"{self.bey_api_key[:4]}...{self.bey_api_key[-4:]}" if self.bey_api_key else "None"
        logger.info(f"Initialized SpecialistAgent {self.config.name} with Beyond Presence Key: {bey_short}")


        self.model = None
        self.session = None
        self.room = None
        self.audio_out_source = None
        self.audio_out_track = None
        self.avatar_session = None
        self.is_active = False

    async def start(self, room: rtc.Room):
        """Initialize and start the specialist agent in the room."""
        self.room = room
        logger.info(f"Starting Specialist Agent: {self.config.name}")

        # Create audio output for this specialist
        self.audio_out_source = rtc.AudioSource(24000, 1)
        self.audio_out_track = rtc.LocalAudioTrack.create_audio_track(
            f"specialist-{self.config.name.lower()}-voice", self.audio_out_source
        )
        await room.local_participant.publish_track(self.audio_out_track)
        logger.info(f"Published {self.config.name}'s audio track")

        # Initialize Gemini model for this specialist
        self.model = realtime.RealtimeModel(
            instructions=self.config.system_prompt,
            model="gemini-2.0-flash-exp",
            voice=self.config.voice,  # Use specialist's unique voice
            temperature=0.7,
            api_key=self.google_api_key,
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        
        # Explicitly ensure the session gets the key from the model
        self.session = self.model.session()
        logger.info(f"Gemini Realtime session initialized for {self.config.name}")

        
        # Set up event handlers
        @self.session.on("generation_created")
        def on_generation_created(event: llm.GenerationCreatedEvent):
            asyncio.create_task(self._consume_message_stream(event.message_stream))

        @self.session.on("error")
        def on_error(e):
            logger.error(f"{self.config.name} Session Error: {e}")

        # Initialize Beyond Presence Avatar for this specialist
        self.avatar_session = bey.AvatarSession(
            avatar_id=self.config.avatar_id,
            api_key=self.bey_api_key,
            avatar_participant_identity=self.config.name.lower(), # Using name as identity (matches frontend keywords)
            avatar_participant_name=self.config.name
        )

        
        # Create a mock agent for Bey to attach to
        class MockAgent:
            def __init__(self, audio_source):
                self.output = type('obj', (object,), {'audio': None})()
                self.audio_out_source = audio_source
        
        mock_agent = MockAgent(self.audio_out_source)
        
        # Attempt to start avatar session with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.avatar_session.start(mock_agent, room=room)
                logger.info(f"{self.config.name}'s avatar started")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to start {self.config.name}'s avatar after {max_retries} attempts: {e}")
                else:
                    logger.warning(f"Connection attempt {attempt+1} failed for {self.config.name}: {e}. Retrying in 3s...")
                    await asyncio.sleep(3)


        self.is_active = True

    async def speak(self, message: str):
        """Have the specialist speak a message."""
        if not self.session:
            logger.error(f"{self.config.name} session not initialized")
            return
        
        logger.info(f"{self.config.name} speaking: {message[:50]}...")
        # Send message to Gemini to generate audio response
        self.session.send_text(message)

    async def _consume_message_stream(self, message_stream):
        """Process audio from Gemini."""
        try:
            async for message in message_stream:
                asyncio.create_task(self._consume_audio_stream(message.audio_stream))
        except Exception as e:
            logger.error(f"Error in {self.config.name}'s message stream: {e}")

    async def _consume_audio_stream(self, stream: utils.aio.Chan[rtc.AudioFrame]):
        """Capture audio and send to avatar."""
        try:
            async for frame in stream:
                if self.avatar_session and hasattr(self.avatar_session, '_data_audio_output'):
                    await self.avatar_session._data_audio_output.capture_frame(frame)
                else:
                    await self.audio_out_source.capture_frame(frame)
        except Exception as e:
            logger.error(f"Error in {self.config.name}'s audio stream: {e}")

    async def stop(self):
        """Clean up the specialist agent."""
        self.is_active = False
        # TODO: Implement proper cleanup


class MultiAgentOrchestrator:
    """
    Orchestrates the Host agent and dynamically spawns Specialist agents.
    """

    """
    Orchestrates the Host agent and dynamically spawns Specialist agents.
    """

    def __init__(self, host_agent, room: rtc.Room, google_api_key: str, api_key_1: str, api_key_2: str = None):
        self.host_agent = host_agent
        self.room = room
        self.google_api_key = google_api_key
        self.api_key_1 = api_key_1
        self.api_key_2 = api_key_2 or api_key_1 # Fallback to key 1 if key 2 is not provided

        # Log redacted keys for orchestrator
        k1_short = f"{self.api_key_1[:4]}...{self.api_key_1[-4:]}" if self.api_key_1 else "None"
        k2_short = f"{self.api_key_2[:4]}...{self.api_key_2[-4:]}" if self.api_key_2 else "None"
        logger.info(f"Orchestrator initialized with K1: {k1_short}, K2: {k2_short}")


        self.active_specialists: Dict[str, SpecialistAgent] = {}
        self.memory = get_memory_manager()

    async def invoke_specialist(self, specialist_id: str, context: str = "", introduce: bool = True) -> bool:
        """
        Bring a specialist into the conversation.
        Returns True if successful.
        """
        if specialist_id in self.active_specialists:
            logger.info(f"Specialist {specialist_id} is already in the room")
            return True

        config = SPECIALISTS.get(specialist_id)
        if not config:
            logger.error(f"Unknown specialist: {specialist_id}")
            return False

        logger.info(f"Invoking specialist: {config.name} ({config.role})")

        # Determine which API key to use
        bey_api_key_to_use = self.api_key_2 if config.beyond_presence_api_key_id == 2 else self.api_key_1

        specialist = SpecialistAgent(config, bey_api_key_to_use, self.google_api_key)

        try:
            await specialist.start(self.room)
            self.active_specialists[specialist_id] = specialist

            # Have the specialist introduce themselves if requested
            if introduce:
                intro_message = f"Olá! Sou {config.name}, {config.role}. {context}"
                await specialist.speak(intro_message)

            return True
        except Exception as e:
            logger.error(f"Failed to invoke specialist {specialist_id}: {e}")
            return False

    async def start_all_specialists(self):
        """Start all configured specialists sequentially with delays to avoid API limits."""
        logger.info("Starting all specialists sequentially with 5s delay...")
        for spec_id in SPECIALISTS.keys():
            await self.invoke_specialist(spec_id, introduce=False)
            # Increased delay to avoid overlapping Beyond Presence session initializations
            await asyncio.sleep(5.0)
        
        logger.info("All specialists started sequentially.")



    async def dismiss_specialist(self, specialist_id: str):
        """Remove a specialist from the conversation."""
        if specialist_id in self.active_specialists:
            specialist = self.active_specialists.pop(specialist_id)
            await specialist.stop()
            logger.info(f"Dismissed specialist: {specialist_id}")

    async def route_to_specialist(self, topic: str) -> Optional[str]:
        """
        Analyze a topic and determine if a specialist should be invoked.
        Returns the specialist_id if one should be brought in, None otherwise.
        """
        config = get_specialist_for_topic(topic)
        if config:
            for spec_id, spec_config in SPECIALISTS.items():
                if spec_config == config:
                    return spec_id
        return None

    def list_active_specialists(self) -> list[str]:
        """List currently active specialist IDs."""
        return list(self.active_specialists.keys())
