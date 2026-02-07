
import asyncio
import logging
import os
from livekit import rtc
from livekit.agents import llm, utils
from livekit.plugins.google import realtime

logger = logging.getLogger("gemini-agent")

class MockOutput:
    def __init__(self, agent):
        self._agent = agent
        self.audio = None

class GeminiMultimodalAgent:
    def __init__(self, model: realtime.RealtimeModel, identity: str = "host"):
        self.model = model
        self.identity = identity.lower()
        self.session = None
        self.room = None
        self.audio_out_source = None
        self.audio_out_track = None
        self.output = MockOutput(self) # Compatibility with Bey plugin

    async def start(self, room: rtc.Room, participant: rtc.RemoteParticipant | None = None):
        self.room = room
        logger.info("Starting Gemini Multimodal Agent")

        # Create Default Audio Output Source (24kHz is Gemini output rate)
        self.audio_out_source = rtc.AudioSource(24000, 1)
        self.audio_out_track = rtc.LocalAudioTrack.create_audio_track(
            "agent-voice", self.audio_out_source
        )
        await room.local_participant.publish_track(self.audio_out_track)
        logger.info("Published agent audio track to room")

        # Initialize Gemini Session
        self.session = self.model.session()
        logger.info("Gemini Realtime session initialized")
        
        
        # Subscribe to generation events (to get audio output)
        @self.session.on("generation_created")
        def on_generation_created(event: llm.GenerationCreatedEvent):
            logger.info(f"Gemini Event: Generation Created (ID: {event.response_id})")
            # message_stream is AsyncIterable[MessageGeneration]
            # Each MessageGeneration has audio_stream
            asyncio.create_task(self._consume_message_stream(event.message_stream))
        
        @self.session.on("error")
        def on_error(e):
            logger.error(f"Gemini Session Error: {e}")

        # Other events for debugging
        @self.session.on("input_audio_transcription_completed")
        def on_transcription(ev):
            logger.info(f"Gemini User Transcription: {ev.transcript}")

        # Subscribe to incoming user audio
        @room.on("track_subscribed")
        def on_track_subscribed(track: rtc.RemoteTrack, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            # Audio routing logic:
            # 1. Never hear yourself
            if participant.identity == self.identity:
                return
            
            # identities of ALL agents
            all_agent_identities = ["cosmo", "maya", "marketing", "ricardo", "finance", "lucas", "product", "fernanda", "legal", "bey-avatar-agent"]
            
            is_agent = participant.identity in all_agent_identities or participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD
            
            if is_agent:
                # Specialized routing:
                if self.identity == "cosmo":
                    # Host hears all authorized agents (specialists)
                    logger.info(f"Host (Cosmo) allowing audio from agent: {participant.identity}")
                elif participant.identity == "cosmo":
                    # Specialists hear the Host
                    logger.info(f"Specialist ({self.identity}) allowing audio from Host: {participant.identity}")
                else:
                    # Specialists ignore other specialists to avoid cross-talk chaos
                    return
                
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Subscribed to audio track from: {participant.identity} (Target: {self.identity})")
                asyncio.create_task(self._forward_audio_to_gemini(track))

        # Handle existing tracks
        all_agent_identities = ["cosmo", "maya", "marketing", "ricardo", "finance", "lucas", "product", "fernanda", "legal", "bey-avatar-agent"]
        for p in room.remote_participants.values():
            if p.identity == self.identity:
                continue
            
            is_agent = p.identity in all_agent_identities or p.kind != rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD
            
            if is_agent:
                if self.identity != "cosmo" and p.identity != "cosmo":
                    continue # Specialists ignore other specialists
            
            for pub in p.track_publications.values():
                if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                    logger.info(f"Found existing audio track for: {p.identity} (Target: {self.identity})")
                    asyncio.create_task(self._forward_audio_to_gemini(pub.track))

    async def _forward_audio_to_gemini(self, track: rtc.RemoteAudioTrack):
        logger.info(f"Starting audio forwarding for track {track.sid}")
        stream = rtc.AudioStream(track)
        frame_count = 0
        async for event in stream:
            # AudioStream yields AudioFrameEvent
            frame = event.frame
            # Gemini RealtimeSession handles resampling internally
            if self.session:
                self.session.push_audio(frame)
            frame_count += 1
            if frame_count % 1000 == 0: 
                logger.debug(f"Pushed {frame_count} frames to Gemini from track {track.sid}")

    async def _consume_message_stream(self, message_stream):
        """Consume message stream and process audio from each message"""
        logger.info("Started consuming Gemini message stream")
        try:
            async for message in message_stream:
                logger.info(f"Received message generation (ID: {message.message_id})")
                # Each message has an audio_stream
                asyncio.create_task(self._consume_audio_stream(message.audio_stream))
        except Exception as e:
            logger.error(f"Error consuming message stream: {e}")

    async def _consume_audio_stream(self, stream: utils.aio.Chan[rtc.AudioFrame]):
        logger.info("Started consuming Gemini audio stream")
        frame_count = 0
        try:
            async for frame in stream:
                # If Bey has overridden output.audio, use it (it might be a DataStreamAudioOutput)
                # It behaves like an AudioSource and has capture_frame
                if self.output.audio and hasattr(self.output.audio, 'capture_frame'):
                    await self.output.audio.capture_frame(frame)
                else:
                    await self.audio_out_source.capture_frame(frame)
                
                frame_count += 1
                if frame_count % 500 == 0:
                    logger.debug(f"Captured {frame_count} audio frames from Gemini")
            logger.info(f"Finished consuming Gemini audio stream. Total frames: {frame_count}")
        except Exception as e:
            logger.error(f"Error consuming audio stream: {e}")

    async def stop(self):
        """Clean up agent resources."""
        logger.info(f"Stopping Gemini agent ({self.identity})")
        if self.session:
            await self.session.aclose()
        if self.room and self.audio_out_track:
            await self.room.local_participant.unpublish_track(self.audio_out_track.sid)
