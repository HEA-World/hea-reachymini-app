import os
import tempfile
import threading
import unittest
import wave
from types import SimpleNamespace

from hea_reachy_mini.speech_executor import (
    MacOSSaySynthesizer,
    SpeechClip,
    SpeechError,
    SpeechExecutor,
    detect_sentence_language,
    normalize_language_code,
)


class FakeSynthesizer:
    def __init__(self, durations=(0.2,)):
        self.durations = list(durations)
        self.paths = []
        self.prepared = False

    def prepare(self):
        self.prepared = True

    def synthesize(self, text, *, language=None):
        descriptor, path = tempfile.mkstemp(prefix="hea_reachy_speech_test_", suffix=".wav")
        os.write(descriptor, b"test audio")
        os.close(descriptor)
        self.paths.append(path)
        duration = self.durations.pop(0)
        return SpeechClip(
            path=path,
            duration_seconds=duration,
            size_bytes=10,
            language=language,
            voice={"nl": "Xander", "es": "Mónica", "en": "Daniel"}.get(language),
        )


class FakeMedia:
    def __init__(self):
        self.played = []
        self.stop_calls = 0

    def play_sound(self, path):
        self.played.append(path)

    def stop_playing(self):
        self.stop_calls += 1


class FakeRobot:
    def __init__(self):
        self.media = FakeMedia()


class SpeechExecutorTests(unittest.TestCase):
    def test_macos_synthesizer_uses_fixed_say_command_and_bounded_pcm_wav(self):
        with tempfile.NamedTemporaryFile() as binary:
            os.chmod(binary.name, 0o700)
            captured = {}

            def run_command(command, **kwargs):
                if command == [binary.name, "-v", "?"]:
                    return SimpleNamespace(
                        returncode=0,
                        stdout=(
                            "Daniel              en_GB    # Hello! My name is Daniel.\n"
                            "Xander              nl_NL    # Hallo! Mijn naam is Xander.\n"
                            "Mónica              es_ES    # ¡Hola! Me llamo Mónica.\n"
                        ),
                    )
                captured.update(command=command, kwargs=kwargs)
                output_path = command[command.index("-o") + 1]
                with wave.open(output_path, "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(22_050)
                    audio.writeframes(b"\x00\x00" * 22_050)
                return SimpleNamespace(returncode=0)

            synthesizer = MacOSSaySynthesizer(
                say_path=binary.name,
                platform_name="darwin",
                run_command=run_command,
            )
            synthesizer.prepare()
            clip = synthesizer.synthesize("  Hallo\n Reachy.  ", language="nl-NL")
            try:
                self.assertEqual(clip.duration_seconds, 1.0)
                self.assertGreater(clip.size_bytes, 44)
                self.assertEqual(captured["command"][0], binary.name)
                self.assertEqual(captured["command"][1:3], ["-v", "Xander"])
                self.assertIn("--file-format=WAVE", captured["command"])
                self.assertIn("--data-format=LEI16@22050", captured["command"])
                self.assertNotIn("shell", captured["kwargs"])
                self.assertEqual(captured["kwargs"]["input"], "Hallo Reachy.")
                self.assertEqual(clip.language, "nl")
                self.assertEqual(clip.voice, "Xander")
            finally:
                clip.discard()
            self.assertFalse(os.path.exists(clip.path))

    def test_non_macos_prepare_fails_without_fallback_provider(self):
        synthesizer = MacOSSaySynthesizer(platform_name="linux")
        with self.assertRaisesRegex(SpeechError, "requires macOS") as raised:
            synthesizer.prepare()
        self.assertEqual(raised.exception.code, "speech_platform_unsupported")

    def test_language_normalization_and_local_fallback_cover_current_hea_languages(self):
        self.assertEqual(normalize_language_code("NL-nl"), "nl")
        self.assertIsNone(normalize_language_code("Dutch; Xander"))
        self.assertEqual(detect_sentence_language("Natuurlijk, ik help je graag met deze vraag."), "nl")
        self.assertEqual(detect_sentence_language("Hola, puedo ayudar con esta pregunta."), "es")
        self.assertEqual(detect_sentence_language("Bonjour, je peux vous aider avec cette question."), "fr")
        self.assertEqual(detect_sentence_language("Natürlich kann ich Ihnen gerne helfen."), "de")
        self.assertEqual(detect_sentence_language("Olá, posso ajudar com esta pergunta."), "pt")

    def test_known_language_without_installed_voice_fails_instead_of_using_english(self):
        with tempfile.NamedTemporaryFile() as binary:
            os.chmod(binary.name, 0o700)

            def run_command(command, **kwargs):
                return SimpleNamespace(
                    returncode=0,
                    stdout="Daniel              en_GB    # Hello! My name is Daniel.\n",
                )

            synthesizer = MacOSSaySynthesizer(
                say_path=binary.name,
                platform_name="darwin",
                run_command=run_command,
            )
            synthesizer.prepare()
            with self.assertRaises(SpeechError) as raised:
                synthesizer.synthesize("Dit is Nederlands.", language="nl")
            self.assertEqual(raised.exception.code, "speech_voice_unavailable")

    def test_sentence_plays_through_reachy_media_while_motion_runs(self):
        now = [0.0]

        def sleep(seconds):
            now[0] += seconds

        synthesizer = FakeSynthesizer([0.2])
        executor = SpeechExecutor(synthesizer=synthesizer, clock=lambda: now[0], sleeper=sleep)
        executor.prepare()
        executor.begin_turn()
        robot = FakeRobot()
        motion_calls = []

        result = executor.speak_with_motion(
            robot,
            "Natuurlijk, ik help je graag.",
            threading.Event(),
            lambda: motion_calls.append("ran") or "completed",
            language="en",
        )

        self.assertEqual(result.speech_outcome, "spoken")
        self.assertEqual(result.motion_outcome, "completed")
        self.assertEqual(result.language, "nl")
        self.assertEqual(result.voice, "Xander")
        self.assertEqual(motion_calls, ["ran"])
        self.assertEqual(len(robot.media.played), 1)
        self.assertEqual(robot.media.stop_calls, 1)
        self.assertFalse(os.path.exists(synthesizer.paths[0]))

    def test_ambiguous_fragment_inherits_current_turn_language_before_metadata(self):
        synthesizer = FakeSynthesizer([0.01, 0.01])
        executor = SpeechExecutor(synthesizer=synthesizer)
        executor.prepare()
        executor.begin_turn()
        robot = FakeRobot()

        first = executor.speak_with_motion(
            robot,
            "This website is simple and works with little traffic.",
            threading.Event(),
            lambda: "no_expression",
            language="en",
        )
        fragment = executor.speak_with_motion(
            robot,
            "(Business owner, Marketing lead, Agency, Client, etc.)",
            threading.Event(),
            lambda: "no_expression",
            language="nl",
        )

        self.assertEqual(first.language, "en")
        self.assertEqual(first.voice, "Daniel")
        self.assertEqual(fragment.language, "en")
        self.assertEqual(fragment.voice, "Daniel")

    def test_confident_language_switch_and_new_turn_metadata_remain_supported(self):
        synthesizer = FakeSynthesizer([0.01, 0.01, 0.01])
        executor = SpeechExecutor(synthesizer=synthesizer)
        executor.prepare()
        executor.begin_turn()
        robot = FakeRobot()

        executor.speak_with_motion(
            robot,
            "This answer starts in English with enough context.",
            threading.Event(),
            lambda: "no_expression",
            language="en",
        )
        switched = executor.speak_with_motion(
            robot,
            "Natuurlijk, ik help je graag met deze vraag.",
            threading.Event(),
            lambda: "no_expression",
            language="en",
        )

        executor.begin_turn()
        new_turn_fragment = executor.speak_with_motion(
            robot,
            "(Marketing, agency, client.)",
            threading.Event(),
            lambda: "no_expression",
            language="es",
        )

        self.assertEqual(switched.language, "nl")
        self.assertEqual(switched.voice, "Xander")
        self.assertEqual(new_turn_fragment.language, "es")
        self.assertEqual(new_turn_fragment.voice, "Mónica")

    def test_stop_interrupts_speech_and_deletes_the_clip(self):
        now = [0.0]
        synthesizer = FakeSynthesizer([1.0])
        robot = FakeRobot()
        executor = None

        def sleep(seconds):
            now[0] += seconds
            executor.stop()

        executor = SpeechExecutor(synthesizer=synthesizer, clock=lambda: now[0], sleeper=sleep)
        executor.prepare()
        executor.begin_turn()
        result = executor.speak_with_motion(
            robot,
            "Stop me.",
            threading.Event(),
            lambda: "motion_disabled",
        )

        self.assertEqual(result.speech_outcome, "stopped")
        self.assertGreaterEqual(robot.media.stop_calls, 1)
        self.assertFalse(os.path.exists(synthesizer.paths[0]))

    def test_turn_duration_budget_fails_before_playback_and_deletes_clip(self):
        synthesizer = FakeSynthesizer([0.8])
        executor = SpeechExecutor(synthesizer=synthesizer, max_turn_seconds=0.5)
        executor.prepare()
        executor.begin_turn()
        robot = FakeRobot()

        with self.assertRaises(SpeechError) as raised:
            executor.speak_with_motion(robot, "Too long.", threading.Event(), lambda: "completed")

        self.assertEqual(raised.exception.code, "speech_turn_budget_exceeded")
        self.assertEqual(robot.media.played, [])
        self.assertFalse(os.path.exists(synthesizer.paths[0]))

    def test_missing_reachy_audio_backend_fails_instead_of_claiming_spoken(self):
        synthesizer = FakeSynthesizer([0.2])
        executor = SpeechExecutor(synthesizer=synthesizer)
        executor.prepare()
        executor.begin_turn()
        media = FakeMedia()
        media.audio = None
        robot = SimpleNamespace(media=media)

        with self.assertRaises(SpeechError) as raised:
            executor.speak_with_motion(robot, "Can you hear me?", threading.Event(), lambda: "completed")

        self.assertEqual(raised.exception.code, "speech_media_unavailable")
        self.assertEqual(media.played, [])
        self.assertFalse(os.path.exists(synthesizer.paths[0]))


if __name__ == "__main__":
    unittest.main()
