"""Voice primitives for ContextHarness voice-to-text interface.

These primitives support voice input functionality, enabling users
to speak to the agent instead of typing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid


class VoiceSource(Enum):
    """Source of voice transcription."""

    WEB_SPEECH_API = "web_speech_api"  # Browser native
    WHISPER_LOCAL = "whisper_local"  # Local Whisper model
    WHISPER_API = "whisper_api"  # OpenAI Whisper API
    OTHER = "other"


class TranscriptionStatus(Enum):
    """Status of a transcription."""

    RECORDING = "recording"  # Currently recording
    PROCESSING = "processing"  # Being transcribed
    COMPLETE = "complete"  # Transcription finished
    ERROR = "error"  # Transcription failed
    CANCELLED = "cancelled"  # User cancelled


@dataclass
class VoiceTranscription:
    """Result of voice-to-text transcription.

    Represents a single transcription of spoken audio to text.

    Attributes:
        id: Unique identifier for this transcription
        text: The transcribed text
        confidence: Confidence score (0.0 to 1.0)
        duration_ms: Duration of the audio in milliseconds
        source: What service performed the transcription
        status: Current status of the transcription
        timestamp: When the transcription was created
        language: Detected or specified language code
        alternatives: Alternative transcriptions with lower confidence
        metadata: Additional metadata from the transcription service
    """

    id: str
    text: str
    confidence: float
    duration_ms: int
    source: VoiceSource
    status: TranscriptionStatus = TranscriptionStatus.COMPLETE
    timestamp: datetime = field(default_factory=datetime.now)
    language: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        text: str,
        confidence: float,
        duration_ms: int,
        source: VoiceSource,
        language: Optional[str] = None,
    ) -> "VoiceTranscription":
        """Create a new transcription with auto-generated ID.

        Args:
            text: Transcribed text
            confidence: Confidence score
            duration_ms: Audio duration
            source: Transcription source
            language: Language code

        Returns:
            A new VoiceTranscription instance
        """
        return cls(
            id=f"vt_{uuid.uuid4().hex[:12]}",
            text=text,
            confidence=confidence,
            duration_ms=duration_ms,
            source=source,
            language=language,
        )

    @classmethod
    def from_web_speech_api(
        cls,
        text: str,
        confidence: float,
        alternatives: Optional[List[str]] = None,
    ) -> "VoiceTranscription":
        """Create a transcription from Web Speech API result.

        Args:
            text: Transcribed text
            confidence: Confidence score
            alternatives: Alternative transcriptions

        Returns:
            A new VoiceTranscription instance
        """
        transcription = cls(
            id=f"vt_{uuid.uuid4().hex[:12]}",
            text=text,
            confidence=confidence,
            duration_ms=0,  # Web Speech API doesn't provide duration
            source=VoiceSource.WEB_SPEECH_API,
        )
        if alternatives:
            transcription.alternatives = alternatives
        return transcription

    @classmethod
    def from_whisper(
        cls,
        text: str,
        duration_ms: int,
        language: str,
        is_local: bool = True,
    ) -> "VoiceTranscription":
        """Create a transcription from Whisper result.

        Args:
            text: Transcribed text
            duration_ms: Audio duration
            language: Detected language
            is_local: Whether local or API Whisper was used

        Returns:
            A new VoiceTranscription instance
        """
        return cls(
            id=f"vt_{uuid.uuid4().hex[:12]}",
            text=text,
            confidence=1.0,  # Whisper doesn't provide confidence
            duration_ms=duration_ms,
            source=VoiceSource.WHISPER_LOCAL if is_local else VoiceSource.WHISPER_API,
            language=language,
        )

    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if transcription has high confidence.

        Args:
            threshold: Minimum confidence threshold

        Returns:
            True if confidence meets threshold
        """
        return self.confidence >= threshold


@dataclass
class VoiceRecordingState:
    """State of an active voice recording.

    Used to track the current recording session in the UI.

    Attributes:
        is_recording: Whether currently recording
        started_at: When recording started
        duration_ms: Current duration
        volume_level: Current audio volume (0.0 to 1.0)
        error: Error message if recording failed
    """

    is_recording: bool = False
    started_at: Optional[datetime] = None
    duration_ms: int = 0
    volume_level: float = 0.0
    error: Optional[str] = None

    def start(self) -> None:
        """Start recording."""
        self.is_recording = True
        self.started_at = datetime.now()
        self.duration_ms = 0
        self.error = None

    def stop(self) -> int:
        """Stop recording and return duration.

        Returns:
            Recording duration in milliseconds
        """
        if self.started_at:
            self.duration_ms = int(
                (datetime.now() - self.started_at).total_seconds() * 1000
            )
        self.is_recording = False
        return self.duration_ms

    def set_error(self, error: str) -> None:
        """Set an error and stop recording.

        Args:
            error: Error message
        """
        self.is_recording = False
        self.error = error

    def update_volume(self, level: float) -> None:
        """Update the current volume level.

        Args:
            level: Volume level (0.0 to 1.0)
        """
        self.volume_level = max(0.0, min(1.0, level))


@dataclass
class VoiceSettings:
    """User settings for voice input.

    Attributes:
        enabled: Whether voice input is enabled
        auto_send: Automatically send after transcription
        language: Preferred language for transcription
        preferred_source: Preferred transcription source
        noise_threshold: Minimum volume to detect speech
        silence_timeout_ms: How long to wait after silence
    """

    enabled: bool = True
    auto_send: bool = False
    language: str = "en-US"
    preferred_source: VoiceSource = VoiceSource.WEB_SPEECH_API
    noise_threshold: float = 0.1
    silence_timeout_ms: int = 1500

    def with_language(self, language: str) -> "VoiceSettings":
        """Create a copy with a different language.

        Args:
            language: New language code

        Returns:
            New VoiceSettings with updated language
        """
        return VoiceSettings(
            enabled=self.enabled,
            auto_send=self.auto_send,
            language=language,
            preferred_source=self.preferred_source,
            noise_threshold=self.noise_threshold,
            silence_timeout_ms=self.silence_timeout_ms,
        )
