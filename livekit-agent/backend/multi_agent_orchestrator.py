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

    def __init__(self, config: SpecialistConfig, api_key: str):
        self.config = config
        self.api_key = api_key
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
            voice=self.config.voice,  # Use specialist's unique voice
            temperature=0.7,
            api_key=self.api_key,
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )

        self.session = self.model.session()
        
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
            # Use a different identity so it appears as a separate participant
        )
        
        # Create a mock agent for Bey to attach to
        class MockAgent:
            def __init__(self, audio_source):
                self.output = type('obj', (object,), {'audio': None})()
                self.audio_out_source = audio_source
        
        mock_agent = MockAgent(self.audio_out_source)
        
        try:
            await self.avatar_session.start(mock_agent, room=room)
            logger.info(f"{self.config.name}'s avatar started")
        except Exception as e:
            logger.error(f"Failed to start {self.config.name}'s avatar: {e}")

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

    def __init__(self, host_agent, room: rtc.Room, api_key: str):
        self.host_agent = host_agent
        self.room = room
        self.api_key = api_key
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

        specialist = SpecialistAgent(config, self.api_key)
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
        """Start all configured specialists silently."""
        logger.info("Starting all specialists...")
        tasks = []
        for spec_id in SPECIALISTS.keys():
            tasks.append(self.invoke_specialist(spec_id, introduce=False))
        
        await asyncio.gather(*tasks)
        logger.info("All specialists started.")

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
