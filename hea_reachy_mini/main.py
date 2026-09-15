"""Daemon-managed HEAGuide app for Reachy Mini Lite."""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import BaseModel, Field
from reachy_mini import ReachyMini, ReachyMiniApp

from .app_state import AppStateStore
from .config import HEA_CREATOR_ID, HEA_ID, MAX_USER_INPUT_CHARS
from .cue_contract import CueGate, CueSelection
from .hea_directory import HeaDirectoryClient, HeaDirectoryError, PublicHea, default_public_hea
from .hea_client import HeaCancelled, HeaClient, HeaClientError
from .motion_executor import MotionExecutor, OfficialMoveLibraryError
from .safe_logging import safe_log
from .speech_executor import SpeechError, SpeechExecutor


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_USER_INPUT_CHARS)
    speak: bool = True
    voice_profile: str = Field(default="auto", pattern=r"^(auto|masculine|feminine)$")


class PreviewCueRequest(BaseModel):
    cue: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    run_motion: bool = False


class SelectHeaRequest(BaseModel):
    creator_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    hea_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class TurnJob:
    question: str
    speak: bool
    voice_profile: str = "auto"
    creator_id: str = HEA_CREATOR_ID
    hea_id: str = HEA_ID
    visitor_id: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class CuePreviewJob:
    selection: CueSelection
    run_motion: bool


class HeaReachyMini(ReachyMiniApp):
    custom_app_url: str | None = "http://127.0.0.1:8042"
    request_media_backend: str | None = None

    def __init__(self, running_on_wireless: bool = False) -> None:
        super().__init__(running_on_wireless=running_on_wireless)
        self.state = AppStateStore()
        self.client = HeaClient()
        self.cue_gate = CueGate()
        self.motion = MotionExecutor()
        self.speech = SpeechExecutor()
        self.directory_client = HeaDirectoryClient()
        self._jobs: queue.Queue[TurnJob | CuePreviewJob] = queue.Queue(maxsize=1)
        self._turn_cancel = threading.Event()
        self._control_lock = threading.RLock()
        self._directory_entries: dict[tuple[str, str], PublicHea] = {}
        self._selected_hea: PublicHea | None = None
        self._visitor_id = f"reachy_lite_visitor_{uuid.uuid4().hex}"
        self._session_id = f"reachy_lite_session_{uuid.uuid4().hex}"
        self._register_routes()

    def _register_routes(self) -> None:
        if self.settings_app is None:
            raise RuntimeError("Reachy settings app is unavailable")

        @self.settings_app.get("/state")
        def get_state() -> dict:
            return self.state.snapshot()

        @self.settings_app.get("/diagnostics")
        def get_diagnostics() -> dict:
            return self.state.diagnostics_snapshot()

        @self.settings_app.get("/heas")
        def get_heas() -> dict:
            return self._directory_payload()

        @self.settings_app.post("/refresh-heas")
        def refresh_heas() -> dict:
            if not self._refresh_directory():
                raise HTTPException(status_code=409, detail="Wait for the active answer before refreshing HEAs")
            return self._directory_payload()

        @self.settings_app.post("/select-hea")
        def select_hea(request: SelectHeaRequest) -> dict:
            return self._select_public_hea(request.creator_id, request.hea_id)

        @self.settings_app.post("/ask", status_code=202)
        def ask(request: AskRequest) -> dict:
            question = request.text.strip()
            if not question:
                raise HTTPException(status_code=400, detail="Enter a question first")
            with self._control_lock:
                snapshot = self.state.snapshot()
                if snapshot["directory"]["status"] != "ready":
                    raise HTTPException(status_code=503, detail="Load the public HEA directory before asking")
                selection = self._selected_hea
                if selection is None or selection.key not in self._directory_entries:
                    raise HTTPException(status_code=409, detail="Choose a public HEA before asking")
                turn_id = self.state.try_queue_turn()
                if turn_id is None:
                    snapshot = self.state.snapshot()
                    if snapshot["stopped"]:
                        raise HTTPException(status_code=409, detail="Resume the app before asking")
                    if snapshot["busy"]:
                        raise HTTPException(status_code=409, detail="A HEA turn is already active")
                    raise HTTPException(status_code=503, detail="Robot is not ready")

                self._turn_cancel.clear()
                self.motion.resume()
                self.speech.resume()
                try:
                    self._jobs.put_nowait(
                        TurnJob(
                            question=question,
                            speak=request.speak,
                            voice_profile=request.voice_profile,
                            creator_id=selection.creator_id,
                            hea_id=selection.hea_id,
                            visitor_id=self._visitor_id,
                            session_id=self._session_id,
                        )
                    )
                except queue.Full as error:
                    self.state.fail(code="turn_queue_full", message="A HEA turn is already queued", request_id=None)
                    raise HTTPException(status_code=409, detail="A HEA turn is already queued") from error
            return {"accepted": True, "turn_id": turn_id}

        @self.settings_app.post("/stop")
        def stop() -> dict:
            self._turn_cancel.set()
            self.motion.stop()
            self.speech.stop()
            self.client.cancel()
            self.state.stop()
            self.state.set_speech_status("stopped")
            return {"stopped": True, "neutral": "next_safe_sdk_boundary"}

        @self.settings_app.post("/preview-cue", status_code=202)
        def preview_cue(request: PreviewCueRequest) -> dict:
            selection = self.cue_gate.select_local_preview(
                request.cue,
                f"local_preview_{uuid.uuid4().hex}",
            )
            if selection is None:
                raise HTTPException(status_code=400, detail="Cue is not in the local canonical catalog")
            if not self.state.try_queue_preview():
                snapshot = self.state.snapshot()
                if snapshot["stopped"]:
                    raise HTTPException(status_code=409, detail="Resume the app before previewing a cue")
                if snapshot["busy"]:
                    raise HTTPException(status_code=409, detail="A HEA turn or cue preview is already active")
                raise HTTPException(status_code=503, detail="Robot is not ready")

            self._turn_cancel.clear()
            self.motion.resume()
            try:
                self._jobs.put_nowait(CuePreviewJob(selection=selection, run_motion=request.run_motion))
            except queue.Full as error:
                self.state.fail(code="preview_queue_full", message="A cue preview is already queued", request_id=None)
                raise HTTPException(status_code=409, detail="A cue preview is already queued") from error
            return {"accepted": True, "cue": selection.cue, "motion_requested": request.run_motion}

        @self.settings_app.post("/resume")
        def resume() -> dict:
            if not self.state.try_resume():
                raise HTTPException(status_code=409, detail="Wait for the active turn to stop")
            self._turn_cancel.clear()
            self.motion.resume()
            self.speech.resume()
            self.state.set_speech_status("ready" if self.speech.available else "unavailable")
            return {"stopped": False}

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        try:
            self.motion.prepare()
        except OfficialMoveLibraryError as error:
            self.state.fail(code="official_move_library_unavailable", message=str(error), request_id=None)
            return
        try:
            self.speech.prepare()
            self.state.set_speech_available(True)
        except SpeechError as error:
            self.state.set_speech_available(False, error=error.code)
            safe_log("spoken_output_unavailable", code=error.code)
        self._refresh_directory()
        self.state.set_robot_ready(True)
        try:
            while not stop_event.is_set():
                try:
                    job = self._jobs.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    if isinstance(job, CuePreviewJob):
                        self._run_cue_preview(reachy_mini, stop_event, job)
                    else:
                        self._run_turn(reachy_mini, stop_event, job)
                finally:
                    self._jobs.task_done()
        finally:
            self._turn_cancel.set()
            self.client.cancel()
            self.motion.stop()
            self.speech.stop()
            try:
                self.motion.neutralize(reachy_mini)
            finally:
                self.state.set_robot_ready(False)

    def _run_turn(self, reachy_mini: ReachyMini, stop_event: threading.Event, job: TurnJob) -> None:
        if self._turn_cancel.is_set() or stop_event.is_set():
            self.state.finish_stopped()
            return

        active_stage = "hea_stream"
        active_sentence_index: int | None = None
        active_cue: str | None = None
        active_request_id: str | None = None
        self.speech.begin_turn()
        self.motion.begin_turn()
        self.state.set_status("answering")

        def on_delta(delta: str) -> None:
            self.state.append_answer(delta)

        def on_sentence(event: dict) -> None:
            nonlocal active_cue, active_request_id, active_sentence_index, active_stage
            active_stage = "sentence_accept"
            sentence = str(event.get("text") or "").strip()
            accepted = self.cue_gate.accept_sentence(event)
            if accepted is None or not sentence or self._turn_cancel.is_set() or stop_event.is_set():
                return
            selection = accepted.selection
            active_sentence_index = accepted.sentence_index
            active_cue = selection.cue if selection is not None else None
            active_request_id = str(event.get("request_id") or "")[:128] or None
            rendered_motion_cue = None

            combined_stop = self._combined_stop_event(stop_event)

            def run_motion(*, speaking: bool) -> str:
                nonlocal active_stage, rendered_motion_cue
                if selection is None:
                    self.state.set_status("speaking" if speaking else "answering")
                    return "no_expression"
                active_stage = "motion_during_speech" if speaking else "motion_fallback"
                self.state.set_status("speaking_and_moving" if speaking else "moving")
                playback = self.motion.execute_cadenced(reachy_mini, selection, combined_stop)
                rendered_motion_cue = playback.motion_cue
                return playback.outcome

            speech_outcome = "disabled" if not job.speak else "unavailable"
            speech_language = accepted.language
            speech_voice = None
            motion_outcome = "no_expression"
            if job.speak and self.speech.available:
                active_stage = "speech_and_motion"
                self.state.set_status("synthesizing")
                self.state.set_speech_status("synthesizing")
                try:
                    playback = self.speech.speak_with_motion(
                        reachy_mini,
                        sentence,
                        combined_stop,
                        lambda: run_motion(speaking=True),
                        language=accepted.language,
                        voice_profile=job.voice_profile,
                    )
                    speech_outcome = playback.speech_outcome
                    motion_outcome = playback.motion_outcome
                    speech_language = playback.language or accepted.language
                    speech_voice = playback.voice
                    self.state.set_speech_status(
                        "stopped" if speech_outcome == "stopped" else "ready",
                        language=speech_language,
                        voice=speech_voice,
                    )
                except SpeechError as error:
                    speech_outcome = error.code
                    self.state.set_speech_status("degraded", error=error.code)
                    safe_log(
                        "sentence_speech_degraded",
                        code=error.code,
                        sentenceIndex=int(event.get("sentence_index") or 0),
                        requestId=event.get("request_id"),
                    )
                    if not combined_stop.is_set():
                        motion_outcome = run_motion(speaking=False)
            else:
                self.state.set_speech_status("disabled" if not job.speak else "unavailable")
                motion_outcome = run_motion(speaking=False)

            active_stage = "sentence_record"
            self.state.record_sentence(
                selection.cue if selection is not None else None,
                selection.emoji if selection is not None else None,
                accepted.sentence_index,
                motion_outcome,
                speech_outcome,
                sentence,
                speech_language,
                speech_voice,
                rendered_motion_cue,
            )
            self.state.set_status("answering")
            active_stage = "hea_stream"

        try:
            result = self.client.ask(
                job.question,
                visitor_id=job.visitor_id or self._visitor_id,
                session_id=job.session_id or self._session_id,
                creator_id=job.creator_id,
                hea_id=job.hea_id,
                cancel_event=self._turn_cancel,
                on_delta=on_delta,
                on_sentence=on_sentence,
            )
            if self._turn_cancel.is_set() or stop_event.is_set():
                self.state.finish_stopped()
                return
            self.state.complete(answer=result.answer, request_id=result.request_id)
        except HeaCancelled:
            self.state.finish_stopped()
        except HeaClientError as error:
            self.state.fail(
                code=error.code,
                message=str(error),
                request_id=error.request_id,
            )
            safe_log(
                "turn_failed",
                code=error.code,
                http=error.http,
                requestId=error.request_id,
            )
        except Exception as error:
            stopping = self._turn_cancel.is_set() or stop_event.is_set()
            code = "turn_stopped_after_local_exception" if stopping else "local_app_error"
            if stopping:
                self.state.finish_stopped()
                safe_log(
                    "stop_completed_after_local_exception",
                    name=type(error).__name__,
                    code=code,
                    requestId=active_request_id,
                    stage=active_stage,
                    cue=active_cue,
                    sentenceIndex=active_sentence_index,
                )
            else:
                self.state.fail(
                    code="local_app_error",
                    message="The local Reachy app failed",
                    request_id=active_request_id,
                )
                safe_log(
                    "local_app_failure",
                    name=type(error).__name__,
                    code=code,
                    requestId=active_request_id,
                    stage=active_stage,
                    cue=active_cue,
                    sentenceIndex=active_sentence_index,
                )

    def _directory_payload(self) -> dict:
        with self._control_lock:
            directory_state = self.state.snapshot()["directory"]
            selected = self._selected_hea.public_dict() if self._selected_hea is not None else None
            return {
                **directory_state,
                "items": [entry.public_dict() for entry in self._directory_entries.values()],
                "selected": selected,
            }

    def _refresh_directory(self) -> bool:
        with self._control_lock:
            if self.state.snapshot()["busy"]:
                return False
            self._directory_entries = {}
            self.state.set_directory_status("loading")
        try:
            entries = self.directory_client.fetch()
        except HeaDirectoryError as error:
            self.state.set_directory_status("unavailable", error=error.code)
            safe_log(
                "public_directory_unavailable",
                name=type(error).__name__,
                code=error.code,
                http=error.http,
            )
            return True

        with self._control_lock:
            self._directory_entries = {entry.key: entry for entry in entries}
            current_key = self._selected_hea.key if self._selected_hea is not None else None
            current = self._directory_entries.get(current_key) if current_key is not None else None
            if current_key is None:
                current = self._directory_entries.get(default_public_hea().key)
            if current is None:
                self._selected_hea = None
                self.state.clear_hea_selection()
                self._reset_conversation_identity()
            else:
                self._selected_hea = current
                self.state.select_hea(current.public_dict(), clear_conversation=False)
            self.state.set_directory_status("ready", count=len(self._directory_entries))
        return True

    def _select_public_hea(self, creator_id: str, hea_id: str) -> dict:
        key = str(creator_id), str(hea_id)
        with self._control_lock:
            snapshot = self.state.snapshot()
            if snapshot["busy"]:
                raise HTTPException(status_code=409, detail="Wait for the active answer before changing HEAs")
            if snapshot["directory"]["status"] != "ready":
                raise HTTPException(status_code=503, detail="The public HEA directory is unavailable")
            selected = self._directory_entries.get(key)
            if selected is None:
                raise HTTPException(status_code=404, detail="HEA is no longer in the public directory")
            changed = self._selected_hea is None or self._selected_hea.key != selected.key
            if changed:
                if not self.state.select_hea(selected.public_dict()):
                    raise HTTPException(status_code=409, detail="Wait for the active answer before changing HEAs")
                self._selected_hea = selected
                self.cue_gate = CueGate()
                self._reset_conversation_identity()
            else:
                self.state.select_hea(selected.public_dict(), clear_conversation=False)
            return {"selected": selected.public_dict(), "changed": changed}

    def _reset_conversation_identity(self) -> None:
        self._visitor_id = f"reachy_lite_visitor_{uuid.uuid4().hex}"
        self._session_id = f"reachy_lite_session_{uuid.uuid4().hex}"

    def _run_cue_preview(
        self,
        reachy_mini: ReachyMini,
        stop_event: threading.Event,
        job: CuePreviewJob,
    ) -> None:
        if self._turn_cancel.is_set() or stop_event.is_set():
            self.state.finish_stopped()
            return

        selection = job.selection
        try:
            self.state.set_status("moving" if job.run_motion else "previewing")
            outcome = (
                self.motion.execute(reachy_mini, selection, self._combined_stop_event(stop_event))
                if job.run_motion
                else "visual_preview"
            )
            self.state.record_cue(
                selection.cue,
                selection.emoji,
                0,
                outcome,
                f"Local catalog preview: {selection.cue.replace('_', ' ')}",
            )
            if self._turn_cancel.is_set() or stop_event.is_set():
                self.state.finish_stopped()
            else:
                self.state.complete_preview()
        except Exception as error:
            self.state.fail(code="local_preview_error", message="The local cue preview failed", request_id=None)
            safe_log("cue_preview_failure", name=type(error).__name__, code="local_preview_error")

    def _combined_stop_event(self, daemon_stop_event: threading.Event) -> object:
        app_cancel = self._turn_cancel

        class CombinedStop:
            @staticmethod
            def is_set() -> bool:
                return app_cancel.is_set() or daemon_stop_event.is_set()

        return CombinedStop()


if __name__ == "__main__":
    app = HeaReachyMini()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
