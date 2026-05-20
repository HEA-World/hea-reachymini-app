/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

import {
  APP_VERSION,
  DEFAULT_CUE_SET_VERSION,
  DEFAULT_HEA_CREATOR_ID,
  DEFAULT_HEA_ENDPOINT,
  DEFAULT_HEA_ID,
  DEFAULT_REACHY_SDK_MODULE_URL,
  makeDefaultId,
} from "./config.js";
import { streamReachyChat } from "./api/heaReachyClient.js";
import { normalizeCuePlan } from "./cues/reachyEmojiV1.js";
import { connectReachy } from "./reachy/connectReachy.js";
import { MotionExecutor } from "./reachy/motionExecutor.js";
import {
  appendAnswer,
  appendLog,
  getUi,
  previewMotionCue,
  renderCuePlan,
  resetAnswer,
  resetMotionPreview,
  setBusy,
  setConnectionState,
  showMockStage,
  updateMockPose,
} from "./ui/render.js";

const ui = getUi();
let reachyConnection = null;
let activeAbortController = null;
let thinkingTimer = null;
let thinkingLoopActive = false;
const motionExecutor = new MotionExecutor({
  robot: null,
  behaviorProfile: ui.behaviorProfile.value,
  onCueStart: (item, motionPlan) => previewMotionCue(ui, item, motionPlan),
  onLog: (message) => appendLog(ui, "motion", message),
});

init();

function init() {
  ui.endpoint.value = DEFAULT_HEA_ENDPOINT;
  ui.creatorId.value = DEFAULT_HEA_CREATOR_ID;
  ui.heaId.value = DEFAULT_HEA_ID;
  ui.sdkModuleUrl.value = DEFAULT_REACHY_SDK_MODULE_URL;
  ui.visitorId.value = makeDefaultId("reachy_visitor");
  ui.sessionId.value = makeDefaultId("reachy_session");

  ui.connectButton.addEventListener("click", handleConnect);
  ui.stopButton.addEventListener("click", handleStop);
  ui.chatForm.addEventListener("submit", handleSubmit);
  ui.behaviorProfile.addEventListener("change", () => {
    motionExecutor.setBehaviorProfile(ui.behaviorProfile.value);
    appendLog(ui, "profile", ui.behaviorProfile.value);
  });
  ui.robotMode.addEventListener("change", () => {
    showMockStage(ui, ui.robotMode.value !== "reachy");
  });

  showMockStage(ui, true);
  setConnectionState(ui, "idle", "Mock ready");
  appendLog(ui, "app_ready", `version ${APP_VERSION}`);
}

async function handleConnect() {
  setBusy(ui, true);
  setConnectionState(ui, "busy", "Connecting");

  try {
    reachyConnection?.cleanup?.();
    reachyConnection = await connectReachy({
      mode: ui.robotMode.value,
      sdkModuleUrl: ui.sdkModuleUrl.value,
      robotId: ui.robotId.value.trim(),
      videoEl: ui.reachyVideo,
      onLog: (message) => appendLog(ui, "reachy", message),
      onRobotState: (state) => updateMockPose(ui, state),
      onRobotsChanged: (robots) => {
        if (!ui.robotId.value && robots[0]?.id) {
          ui.robotId.placeholder = `available: ${robots[0].id}`;
        }
      },
    });

    motionExecutor.setRobot(reachyConnection.robot);
    showMockStage(ui, ui.robotMode.value !== "reachy");
    setConnectionState(ui, "connected", reachyConnection.connected ? "Connected" : "Login required");
  } catch (error) {
    setConnectionState(ui, "error", "Connection failed");
    appendLog(ui, "connect_error", error.message);
  } finally {
    setBusy(ui, false);
  }
}

async function handleSubmit(event) {
  event.preventDefault();

  if (!reachyConnection) {
    await handleConnect();
  }

  activeAbortController = new AbortController();
  resetAnswer(ui);
  setBusy(ui, true);
  setConnectionState(ui, "busy", "Answering");

  let rawTextBuffer = "";
  let usedSentenceSync = false;
  const sentenceCueItems = [];
  startThinkingLoop();

  try {
    await streamReachyChat({
      endpoint: ui.endpoint.value,
      payload: buildPayload(),
      useMock: ui.mockApi.checked,
      signal: activeAbortController.signal,
      onTextDelta: (delta) => {
        rawTextBuffer += delta;
      },
      onSentenceReady: async (eventPayload) => {
        usedSentenceSync = true;
        stopThinkingLoop();

        if (eventPayload.text) {
          appendAnswer(ui, `${eventPayload.text} `);
        }

        if (eventPayload.cue_item) {
          sentenceCueItems.push(eventPayload.cue_item);
          renderCuePlan(ui, { type: "reachy_cue_plan", items: sentenceCueItems });
          await motionExecutor.runCueItem(eventPayload.cue_item);
        }
      },
      onCuePlan: async (cuePlan) => {
        const normalizedPlan = normalizeCuePlan(cuePlan);
        renderCuePlan(ui, normalizedPlan);
        if (!usedSentenceSync) {
          stopThinkingLoop();
          await motionExecutor.runCuePlan(normalizedPlan);
        }
      },
      onDone: () => {
        stopThinkingLoop();
        if (!usedSentenceSync && rawTextBuffer) {
          appendAnswer(ui, rawTextBuffer);
        }
      },
      onEvent: (eventPayload) => appendLog(ui, eventPayload.type || "event", JSON.stringify(eventPayload)),
    });

    stopThinkingLoop();
    if (!usedSentenceSync && rawTextBuffer && !ui.answer.textContent) {
      appendAnswer(ui, rawTextBuffer);
    }
    setConnectionState(ui, "connected", "Ready");
  } catch (error) {
    stopThinkingLoop();
    if (activeAbortController.signal.aborted) {
      appendLog(ui, "aborted", "Stopped by operator");
      setConnectionState(ui, "connected", "Stopped");
    } else {
      appendLog(ui, "chat_error", error.message);
      setConnectionState(ui, "error", "Chat failed");
    }
  } finally {
    stopThinkingLoop();
    setBusy(ui, false);
  }
}

function handleStop() {
  activeAbortController?.abort();
  stopThinkingLoop();
  motionExecutor.stop();
  resetMotionPreview(ui);
  reachyConnection?.robot?.requestState?.();
  setConnectionState(ui, reachyConnection ? "connected" : "idle", "Stopped");
  appendLog(ui, "safe_stop", "Returned motion executor to neutral pose.");
}

function buildPayload() {
  const payload = {
    install_id: emptyToUndefined(ui.installId.value),
    creator_id: emptyToUndefined(ui.creatorId.value),
    hea_id: emptyToUndefined(ui.heaId.value),
    visitorID: ui.visitorId.value,
    session_id: ui.sessionId.value,
    message: ui.userText.value,
    user_text: ui.userText.value,
    channel: "reachy_mini",
    reachy_cue_session: true,
    reachy_sentence_sync: true,
    cue_set_version: DEFAULT_CUE_SET_VERSION,
    behavior_catalog_id: ui.behaviorProfile.value,
  };

  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

function emptyToUndefined(value) {
  const trimmed = String(value || "").trim();
  return trimmed ? trimmed : undefined;
}

function startThinkingLoop() {
  stopThinkingLoop();
  thinkingLoopActive = true;

  const runThinkingCue = () => {
    if (!thinkingLoopActive) return;
    motionExecutor
      .runCueItem({
        sentence_index: 0,
        emoji: "🤔",
        cue: "thinking",
        intensity: 0.35,
        timing: "during_sentence",
        reason: "local waiting behavior",
      })
      .catch((error) => appendLog(ui, "thinking_error", error.message));
  };

  runThinkingCue();
  thinkingTimer = window.setInterval(runThinkingCue, 1800);
}

function stopThinkingLoop() {
  thinkingLoopActive = false;
  if (thinkingTimer) {
    window.clearInterval(thinkingTimer);
    thinkingTimer = null;
  }
}
