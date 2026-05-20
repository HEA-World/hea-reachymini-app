/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

export function getUi() {
  return {
    answer: document.querySelector("#answer"),
    askButton: document.querySelector("#ask-button"),
    behaviorProfile: document.querySelector("#behavior-profile"),
    chatForm: document.querySelector("#chat-form"),
    connectionLabel: document.querySelector("#connection-label"),
    connectionStatus: document.querySelector("#connection-status"),
    connectButton: document.querySelector("#connect-button"),
    creatorId: document.querySelector("#creator-id"),
    cueList: document.querySelector("#cue-list"),
    endpoint: document.querySelector("#endpoint"),
    eventLog: document.querySelector("#event-log"),
    heaId: document.querySelector("#hea-id"),
    installId: document.querySelector("#install-id"),
    mockRobot: document.querySelector("#mock-robot"),
    mockApi: document.querySelector("#mock-api"),
    mockPose: document.querySelector("#mock-pose"),
    mockStage: document.querySelector("#mock-stage"),
    previewCue: document.querySelector("#preview-cue"),
    promptButtons: document.querySelectorAll("[data-prompt]"),
    reachyVideo: document.querySelector("#reachy-video"),
    robotId: document.querySelector("#robot-id"),
    robotMode: document.querySelector("#robot-mode"),
    sdkModuleUrl: document.querySelector("#sdk-module-url"),
    sessionId: document.querySelector("#session-id"),
    stopButton: document.querySelector("#stop-button"),
    userText: document.querySelector("#user-text"),
    visitorId: document.querySelector("#visitor-id"),
  };
}

let previewTimer = null;

export function setConnectionState(ui, state, label) {
  ui.connectionStatus.dataset.state = state;
  ui.connectionLabel.textContent = label;
}

export function setBusy(ui, busy) {
  ui.askButton.disabled = busy;
  ui.connectButton.disabled = busy;
}

export function resetAnswer(ui) {
  ui.answer.textContent = "";
  ui.cueList.replaceChildren();
  resetMotionPreview(ui);
}

export function appendAnswer(ui, text) {
  ui.answer.textContent += text;
}

export function renderCuePlan(ui, cuePlan) {
  ui.cueList.replaceChildren();

  cuePlan.items.forEach((item) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <strong>${escapeHtml(item.emoji)} ${escapeHtml(item.cue)}</strong>
      <span class="cue-meta">sentence ${item.sentence_index + 1} - intensity ${item.intensity}</span>
      ${item.reason ? `<span>${escapeHtml(item.reason)}</span>` : ""}
    `;
    ui.cueList.append(li);
  });
}

export function appendLog(ui, label, detail = "") {
  const li = document.createElement("li");
  const time = new Date().toLocaleTimeString();
  li.innerHTML = `
    <span class="event-meta">${escapeHtml(time)} - ${escapeHtml(label)}</span>
    ${detail ? `<code>${escapeHtml(detail)}</code>` : ""}
  `;
  ui.eventLog.prepend(li);

  while (ui.eventLog.children.length > 80) {
    ui.eventLog.lastElementChild?.remove();
  }
}

export function updateMockPose(ui, state) {
  if (!state) return;
  const head = Array.isArray(state.head) ? state.head : [0, 0, 0];
  const antennas = Array.isArray(state.antennas) ? state.antennas : [0, 0];
  const bodyYaw = Number(state.body_yaw || 0);

  ui.mockPose.textContent = `Head ${formatPose(head)} - Antennas ${formatPose(antennas)} - Body ${bodyYaw.toFixed(1)}`;

  if (ui.mockRobot) {
    ui.mockRobot.style.setProperty("--head-roll", `${Number(head[0] || 0).toFixed(1)}deg`);
    ui.mockRobot.style.setProperty("--head-pitch", `${Number(head[1] || 0).toFixed(1)}deg`);
    ui.mockRobot.style.setProperty("--head-yaw", `${Number(head[2] || 0).toFixed(1)}deg`);
    ui.mockRobot.style.setProperty("--antenna-right", `${Number(antennas[0] || 0).toFixed(1)}deg`);
    ui.mockRobot.style.setProperty("--antenna-left", `${Number(antennas[1] || 0).toFixed(1)}deg`);
    ui.mockRobot.style.setProperty("--body-yaw", `${bodyYaw.toFixed(1)}deg`);
  }
}

export function showMockStage(ui, visible) {
  ui.mockStage.hidden = !visible;
}

export function previewMotionCue(ui, item, motionPlan) {
  if (!ui.mockRobot || !ui.previewCue) return;

  const cue = sanitizeCueName(motionPlan?.cue || item?.cue || "idle");
  const emoji = motionPlan?.emoji || item?.emoji || "";
  const label = motionPlan?.label || cue.replaceAll("_", " ");
  const intensity =
    Number.isFinite(Number(item?.intensity)) ? ` - intensity ${Number(item.intensity).toFixed(2)}` : "";

  window.clearTimeout(previewTimer);
  ui.mockRobot.dataset.cue = "idle";
  void ui.mockRobot.offsetWidth;
  ui.mockRobot.dataset.cue = cue;
  ui.previewCue.textContent = `${emoji ? `${emoji} ` : ""}${label}${intensity}`;

  previewTimer = window.setTimeout(() => {
    resetMotionPreview(ui);
  }, 1800);
}

export function resetMotionPreview(ui) {
  window.clearTimeout(previewTimer);
  previewTimer = null;

  if (ui.mockRobot) {
    ui.mockRobot.dataset.cue = "idle";
  }

  if (ui.previewCue) {
    ui.previewCue.textContent = "Idle expression preview";
  }
}

function formatPose(values) {
  return values.map((value) => Number(value).toFixed(1)).join(" / ");
}

function sanitizeCueName(cue) {
  const normalized = String(cue || "idle").toLowerCase();
  return /^[a-z0-9_-]+$/.test(normalized) ? normalized : "idle";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
