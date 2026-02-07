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


        self.agent = None
        self.room = None
        self.avatar_session = None
        self.is_active = False

    async def start(self, room: rtc.Room):
        """Initialize and start the specialist agent in the room."""
        self.room = room
        logger.info(f"Starting Specialist Agent: {self.config.name}")

        # Initialize Gemini model for this specialist
        model = realtime.RealtimeModel(
            instructions=self.config.system_prompt,
            model="gemini-2.0-flash-exp",
            voice=self.config.voice,  # Use specialist's unique voice
            temperature=0.7,
            api_key=self.google_api_key,
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        
        from backend.gemini_agent import GeminiMultimodalAgent
        self.agent = GeminiMultimodalAgent(model=model, identity=self.config.name.lower())
        
        await self.agent.start(room)
        logger.info(f"Gemini agent started for {self.config.name}")

        # Initialize Beyond Presence Avatar for this specialist
        self.avatar_session = bey.AvatarSession(
            avatar_id=self.config.avatar_id,
            api_key=self.bey_api_key,
            avatar_participant_identity=self.config.name.lower(), # Using name as identity (matches frontend keywords)
            avatar_participant_name=self.config.name
        )

        
        # Attempt to start avatar session with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # bey plugin will attach to self.agent and override its output.audio
                await self.avatar_session.start(self.agent, room=room)
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
        if not self.agent or not self.agent.session:
            logger.error(f"{self.config.name} agent not initialized")
            return
        
        logger.info(f"{self.config.name} speaking: {message[:50]}...")
        self.agent.session.send_text(message)

    async def stop(self):
        """Clean up the specialist agent."""
        logger.info(f"Stopping Specialist Agent: {self.config.name}")
        self.is_active = False
        
        try:
            # 1. Stop Avatar Session
            if self.avatar_session:
                await self.avatar_session.stop()
                logger.info(f"{self.config.name}'s avatar session stopped")
            
            # 2. Stop Gemini Agent (includes track unpublishing and session closing)
            if self.agent:
                # We need a stop method in GeminiMultimodalAgent too for full cleanup
                if hasattr(self.agent, 'stop'):
                    await self.agent.stop()
                elif self.agent.session:
                    await self.agent.session.aclose()
                
                if self.room and self.agent.audio_out_track:
                    await self.room.local_participant.unpublish_track(self.agent.audio_out_track.sid)
                
                logger.info(f"{self.config.name}'s agent cleaned up")
                
        except Exception as e:
            logger.error(f"Error while stopping {self.config.name}: {e}")


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
        """Start all configured specialists simultaneously using gather."""
        logger.info("Starting all specialists simultaneously...")
        
        tasks = []
        for i, spec_id in enumerate(SPECIALISTS.keys()):
            # Small staggered delay (jitter) to prevent simultaneous API burst, 
            # but much faster than 5s sequential.
            tasks.append(self._start_with_delay(spec_id, delay=i * 1.5))
        
        # Run all initializations in parallel
        await asyncio.gather(*tasks)
        logger.info("All specialists initialization triggered.")

    async def _start_with_delay(self, specialist_id: str, delay: float):
        """Helper to start a specialist after a small delay."""
        await asyncio.sleep(delay)
        return await self.invoke_specialist(specialist_id, introduce=False)



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
