"""Bounded offline speech synthesis and Reachy speaker playback."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import (
    MAX_SPEECH_BYTES,
    MAX_SPEECH_SENTENCE_CHARS,
    MAX_SPEECH_SENTENCE_SECONDS,
    MAX_SPEECH_SYNTHESIS_SECONDS,
    MAX_SPEECH_TURN_SECONDS,
    SPEECH_RATE_WPM,
)


class SpeechError(RuntimeError):
    """Structured local speech failure that is safe to expose without user text."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_language_code(value: object) -> str | None:
    """Return a bounded base ISO language code, never a voice/command value."""

    normalized = str(value or "").strip().lower().replace("_", "-")
    base_language = normalized.split("-", 1)[0]
    return base_language if re.fullmatch(r"[a-z]{2,3}", base_language) else None


def normalize_voice_profile(value: object) -> str:
    """Return one supported local voice preference, never a voice name."""

    normalized = str(value or "auto").strip().lower()
    if normalized not in {"auto", "masculine", "feminine"}:
        raise SpeechError("speech_voice_profile_invalid", "The local voice preference is invalid")
    return normalized


_LANGUAGE_MARKERS = {
    "en": frozenset({"the", "and", "you", "your", "this", "that", "with", "for", "hello", "thanks", "can", "help", "would", "please"}),
    "nl": frozenset({"de", "het", "een", "en", "van", "ik", "jij", "je", "uw", "dit", "dat", "met", "voor", "niet", "kan", "graag", "helpen", "vraag", "antwoord"}),
    "fr": frozenset({"le", "la", "les", "des", "une", "et", "vous", "votre", "ce", "cette", "avec", "pour", "pas", "peux", "aider", "bonjour", "merci"}),
    "de": frozenset({"der", "die", "das", "ein", "eine", "und", "sie", "ihr", "dies", "mit", "für", "nicht", "kann", "helfen", "hallo", "danke"}),
    "es": frozenset({"el", "la", "los", "las", "una", "y", "usted", "tu", "este", "esta", "con", "para", "no", "puedo", "ayudar", "hola", "gracias"}),
    "pt": frozenset({"o", "a", "os", "as", "uma", "e", "você", "seu", "este", "esta", "com", "para", "não", "posso", "ajudar", "olá", "obrigado"}),
}
_DISTINCTIVE_LANGUAGE_MARKERS = {
    "en": frozenset({"hello", "thanks", "please"}),
    "nl": frozenset({"natuurlijk", "graag", "welkom", "dank", "jouw", "jullie"}),
    "fr": frozenset({"bonjour", "merci", "bienvenue", "voici", "peut-être"}),
    "de": frozenset({"hallo", "danke", "natürlich", "willkommen", "gerne"}),
    "es": frozenset({"hola", "gracias", "bienvenido", "puedo", "ayudar"}),
    "pt": frozenset({"olá", "obrigado", "obrigada", "bem-vindo", "posso"}),
}


def detect_sentence_language(text: str) -> str | None:
    """Conservative local fallback for the six current HEA UI languages."""

    words = re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)?", str(text or "").lower(), flags=re.UNICODE)
    if not words:
        return None
    word_set = set(words)
    distinctive = [
        language
        for language, markers in _DISTINCTIVE_LANGUAGE_MARKERS.items()
        if word_set.intersection(markers)
    ]
    if len(distinctive) == 1:
        return distinctive[0]

    scores = {
        language: sum(1 for word in words if word in markers)
        for language, markers in _LANGUAGE_MARKERS.items()
    }
    best_score = max(scores.values(), default=0)
    winners = [language for language, score in scores.items() if score == best_score]
    return winners[0] if best_score >= 2 and len(winners) == 1 else None


@dataclass(frozen=True)
class MacOSVoice:
    name: str
    locale: str

    @property
    def language(self) -> str:
        return self.locale.split("_", 1)[0].lower()


@dataclass(frozen=True)
class SpeechClip:
    path: str
    duration_seconds: float
    size_bytes: int
    language: str | None = None
    voice: str | None = None

    def discard(self) -> None:
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class SpeechPlaybackResult:
    speech_outcome: str
    motion_outcome: str
    language: str | None = None
    voice: str | None = None


class MacOSSaySynthesizer:
    """Generate a temporary PCM WAV through macOS' offline ``say`` service."""

    def __init__(
        self,
        *,
        say_path: str = "/usr/bin/say",
        platform_name: str = sys.platform,
        run_command: Callable[..., Any] = subprocess.run,
    ) -> None:
        self._say_path = say_path
        self._platform_name = platform_name
        self._run_command = run_command
        self._voices_by_language: dict[str, tuple[MacOSVoice, ...]] = {}

    _PREFERRED_VOICES = {
        "en": ("Daniel", "Samantha"),
        "nl": ("Xander", "Ellen"),
        "fr": ("Thomas", "Jacques", "Amélie"),
        "de": ("Anna",),
        "es": ("Mónica",),
        "pt": ("Joana", "Luciana"),
    }
    _PROFILE_VOICES = {
        "masculine": {
            "en": ("Daniel", "Albert", "Fred", "Ralph", "Aman", "Rishi"),
            "nl": ("Xander",),
            "fr": ("Thomas", "Jacques", "Eddy (French (France))", "Reed (French (Canada))"),
            "de": ("Eddy (German (Germany))", "Reed (German (Germany))", "Rocko (German (Germany))"),
            "es": ("Eddy (Spanish (Spain))", "Reed (Spanish (Spain))", "Rocko (Spanish (Spain))"),
            "pt": ("Eddy (Portuguese (Brazil))", "Reed (Portuguese (Brazil))", "Rocko (Portuguese (Brazil))"),
        },
        "feminine": {
            "en": ("Samantha", "Karen", "Kathy", "Moira", "Tessa", "Tara"),
            "nl": ("Ellen",),
            "fr": ("Amélie", "Flo (French (France))", "Sandy (French (France))", "Shelley (French (France))"),
            "de": ("Anna", "Flo (German (Germany))", "Sandy (German (Germany))", "Shelley (German (Germany))"),
            "es": ("Mónica", "Paulina", "Flo (Spanish (Spain))", "Sandy (Spanish (Spain))"),
            "pt": ("Joana", "Luciana", "Flo (Portuguese (Brazil))", "Sandy (Portuguese (Brazil))"),
        },
    }

    def prepare(self) -> None:
        if self._platform_name != "darwin":
            raise SpeechError(
                "speech_platform_unsupported",
                "Spoken output currently requires macOS on Reachy Mini Lite",
            )
        if not os.path.isfile(self._say_path) or not os.access(self._say_path, os.X_OK):
            raise SpeechError("speech_engine_unavailable", "The macOS speech engine is unavailable")

        try:
            result = self._run_command(
                [self._say_path, "-v", "?"],
                text=True,
                capture_output=True,
                timeout=MAX_SPEECH_SYNTHESIS_SECONDS,
                check=False,
            )
        except Exception as error:
            raise SpeechError("speech_voice_inventory_unavailable", "The macOS voice inventory is unavailable") from error
        if int(getattr(result, "returncode", 1)) != 0:
            raise SpeechError("speech_voice_inventory_unavailable", "The macOS voice inventory is unavailable")

        voices_by_language: dict[str, list[MacOSVoice]] = {}
        for line in str(getattr(result, "stdout", "") or "").splitlines():
            match = re.match(r"^(.+?)\s+([a-z]{2,3}_[A-Z]{2})\s+#", line)
            if not match:
                continue
            voice = MacOSVoice(name=match.group(1).strip(), locale=match.group(2))
            voices_by_language.setdefault(voice.language, []).append(voice)
        if not voices_by_language:
            raise SpeechError("speech_voice_inventory_unavailable", "The macOS voice inventory is empty")
        self._voices_by_language = {
            language: tuple(voices)
            for language, voices in voices_by_language.items()
        }

    def select_voice(self, language: str | None, voice_profile: str = "auto") -> MacOSVoice | None:
        normalized = normalize_language_code(language)
        if normalized is None:
            return None
        profile = normalize_voice_profile(voice_profile)
        candidates = self._voices_by_language.get(normalized, ())
        if not candidates:
            raise SpeechError(
                "speech_voice_unavailable",
                f"No installed macOS voice matches language {normalized}",
            )
        preferred_names = (
            self._PREFERRED_VOICES.get(normalized, ())
            if profile == "auto"
            else self._PROFILE_VOICES[profile].get(normalized, ())
        )
        for preferred_name in preferred_names:
            for candidate in candidates:
                if candidate.name == preferred_name:
                    return candidate
        if profile != "auto":
            raise SpeechError(
                "speech_voice_profile_unavailable",
                f"No installed {profile} macOS voice matches language {normalized}",
            )
        return candidates[0]

    def synthesize(
        self,
        text: str,
        *,
        language: str | None = None,
        voice_profile: str = "auto",
    ) -> SpeechClip:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            raise SpeechError("speech_text_empty", "There is no sentence to speak")
        if len(normalized) > MAX_SPEECH_SENTENCE_CHARS:
            raise SpeechError("speech_text_too_large", "The sentence exceeds the local speech limit")

        descriptor, path = tempfile.mkstemp(prefix="hea_reachy_speech_", suffix=".wav")
        os.close(descriptor)
        try:
            voice = self.select_voice(language, voice_profile)
            command = [self._say_path]
            if voice is not None:
                command.extend(["-v", voice.name])
            command.extend(
                [
                    "-r",
                    str(SPEECH_RATE_WPM),
                    "-o",
                    path,
                    "--file-format=WAVE",
                    "--data-format=LEI16@22050",
                    "--channels=1",
                    "-f",
                    "-",
                ]
            )
            result = self._run_command(
                command,
                input=normalized,
                text=True,
                capture_output=True,
                timeout=MAX_SPEECH_SYNTHESIS_SECONDS,
                check=False,
            )
            if int(getattr(result, "returncode", 1)) != 0:
                raise SpeechError("speech_synthesis_failed", "Local speech synthesis failed")

            size_bytes = os.path.getsize(path)
            if size_bytes <= 44 or size_bytes > MAX_SPEECH_BYTES:
                raise SpeechError("speech_audio_size_invalid", "Generated speech audio exceeded its safe bounds")

            with wave.open(path, "rb") as audio:
                frame_rate = audio.getframerate()
                frame_count = audio.getnframes()
                if frame_rate <= 0 or frame_count <= 0:
                    raise SpeechError("speech_audio_invalid", "Generated speech audio is empty")
                duration_seconds = frame_count / frame_rate

            if duration_seconds <= 0 or duration_seconds > MAX_SPEECH_SENTENCE_SECONDS:
                raise SpeechError("speech_duration_exceeded", "Generated speech exceeded the sentence duration limit")

            return SpeechClip(
                path=path,
                duration_seconds=duration_seconds,
                size_bytes=size_bytes,
                language=voice.language if voice is not None else None,
                voice=voice.name if voice is not None else None,
            )
        except SpeechError:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            raise
        except subprocess.TimeoutExpired as error:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            raise SpeechError("speech_synthesis_timeout", "Local speech synthesis timed out") from error
        except Exception as error:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            raise SpeechError("speech_synthesis_failed", "Local speech synthesis failed") from error


class SpeechExecutor:
    """Play synthesized sentences serially and cancel playback through the SDK."""

    def __init__(
        self,
        *,
        synthesizer: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        max_turn_seconds: float = MAX_SPEECH_TURN_SECONDS,
    ) -> None:
        self._synthesizer = synthesizer or MacOSSaySynthesizer()
        self._clock = clock
        self._sleeper = sleeper
        self._max_turn_seconds = max_turn_seconds
        self._state_lock = threading.Lock()
        self._active_media: Any | None = None
        self._available = False
        self._stopped = False
        self._turn_seconds = 0.0
        self._turn_language: str | None = None

    @property
    def available(self) -> bool:
        with self._state_lock:
            return self._available

    def prepare(self) -> None:
        self._synthesizer.prepare()
        with self._state_lock:
            self._available = True

    def begin_turn(self) -> None:
        with self._state_lock:
            self._turn_seconds = 0.0
            self._turn_language = None

    def resume(self) -> None:
        with self._state_lock:
            self._stopped = False

    def stop(self) -> None:
        with self._state_lock:
            self._stopped = True
            active_media = self._active_media
        if active_media is not None:
            try:
                active_media.stop_playing()
            except Exception:
                pass

    def speak_with_motion(
        self,
        reachy_mini: object,
        text: str,
        stop_event: object,
        motion_callback: Callable[[], str],
        language: str | None = None,
        voice_profile: str = "auto",
    ) -> SpeechPlaybackResult:
        with self._state_lock:
            if not self._available:
                raise SpeechError("speech_unavailable", "Spoken output is unavailable")
            if self._stopped or stop_event.is_set():
                return SpeechPlaybackResult("stopped", "stopped")

        requested_language = normalize_language_code(language)
        detected_language = detect_sentence_language(text)
        with self._state_lock:
            # The actual sentence wins when the local detector is confident;
            # a short/ambiguous continuation inherits the current turn before
            # trusting per-sentence metadata. The first ambiguous sentence can
            # still use validated metadata, and begin_turn resets continuity.
            resolved_language = detected_language or self._turn_language or requested_language
            if resolved_language:
                self._turn_language = resolved_language

        clip = self._synthesizer.synthesize(
            text,
            language=resolved_language,
            voice_profile=normalize_voice_profile(voice_profile),
        )
        with self._state_lock:
            if self._turn_seconds + clip.duration_seconds > self._max_turn_seconds:
                clip.discard()
                raise SpeechError("speech_turn_budget_exceeded", "The turn exceeded its spoken-audio budget")
            self._turn_seconds += clip.duration_seconds
            if self._stopped or stop_event.is_set():
                clip.discard()
                return SpeechPlaybackResult("stopped", "stopped", clip.language, clip.voice)

        media = getattr(reachy_mini, "media", None)
        if media is None or (hasattr(media, "audio") and media.audio is None):
            clip.discard()
            raise SpeechError("speech_media_unavailable", "Reachy speaker playback is unavailable")

        with self._state_lock:
            self._active_media = media

        started_at = self._clock()
        try:
            try:
                media.play_sound(clip.path)
            except Exception as error:
                raise SpeechError("speech_playback_failed", "Reachy speaker playback failed") from error

            if self._stopped or stop_event.is_set():
                return SpeechPlaybackResult("stopped", "stopped", clip.language, clip.voice)

            motion_outcome = motion_callback()
            deadline = started_at + clip.duration_seconds
            while self._clock() < deadline:
                if self._stopped or stop_event.is_set():
                    return SpeechPlaybackResult("stopped", motion_outcome, clip.language, clip.voice)
                self._sleeper(min(0.05, max(0.0, deadline - self._clock())))
            return SpeechPlaybackResult("spoken", motion_outcome, clip.language, clip.voice)
        finally:
            try:
                media.stop_playing()
            except Exception:
                pass
            with self._state_lock:
                if self._active_media is media:
                    self._active_media = None
            clip.discard()
