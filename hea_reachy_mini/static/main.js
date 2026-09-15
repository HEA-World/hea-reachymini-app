const ui = {
  form: document.querySelector("#ask-form"),
  question: document.querySelector("#question"),
  speakAnswer: document.querySelector("#speak-answer"),
  ask: document.querySelector("#ask"),
  stop: document.querySelector("#stop"),
  resume: document.querySelector("#resume"),
  answer: document.querySelector("#answer"),
  error: document.querySelector("#error"),
  cues: document.querySelector("#cues"),
  motionAllowlist: document.querySelector("#motion-allowlist"),
  cueCatalog: document.querySelector("#cue-catalog"),
  armMotion: document.querySelector("#arm-motion"),
  requestId: document.querySelector("#request-id"),
  robotStatus: document.querySelector("#robot-status"),
  heaStatus: document.querySelector("#hea-status"),
  speechStatus: document.querySelector("#speech-status"),
  appStatus: document.querySelector("#app-status"),
  robotDot: document.querySelector("#robot-dot"),
  heaDot: document.querySelector("#hea-dot"),
  speechDot: document.querySelector("#speech-dot"),
  appDot: document.querySelector("#app-dot"),
  directoryStatus: document.querySelector("#directory-status"),
  heaSearch: document.querySelector("#hea-search"),
  heaPicker: document.querySelector("#hea-picker"),
  refreshHeas: document.querySelector("#refresh-heas"),
  selectedHeaAvatar: document.querySelector("#selected-hea-avatar"),
  selectedHeaName: document.querySelector("#selected-hea-name"),
  selectedHeaId: document.querySelector("#selected-hea-id"),
  askHeaName: document.querySelector("#ask-hea-name"),
  askButtonHeaName: document.querySelector("#ask-button-hea-name"),
  appVersion: document.querySelector("#app-version"),
  exportDiagnostics: document.querySelector("#export-diagnostics"),
};

let directoryItems = [];
let directoryState = "not_loaded";
let latestState = null;

const labels = {
  starting: "Starting",
  ready: "Ready",
  queued: "Queued",
  answering: "Answering",
  synthesizing: "Synthesizing",
  speaking: "Speaking",
  speaking_and_moving: "Speaking + moving",
  moving: "Moving",
  previewing: "Previewing",
  complete: "Complete",
  stopped: "Stopped",
  error: "Error",
};

const languageNames = {
  de: "German",
  en: "English",
  es: "Spanish",
  fr: "French",
  nl: "Dutch",
  pt: "Portuguese",
};

ui.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await request("/ask", { text: ui.question.value, speak: ui.speakAnswer.checked });
});

ui.stop.addEventListener("click", () => request("/stop"));
ui.resume.addEventListener("click", () => request("/resume"));
ui.exportDiagnostics.addEventListener("click", exportDiagnostics);
ui.refreshHeas.addEventListener("click", async () => {
  await loadDirectory(true);
});
ui.heaSearch.addEventListener("input", () => renderDirectoryOptions());
ui.heaPicker.addEventListener("change", async () => {
  const index = Number(ui.heaPicker.value);
  const selected = Number.isInteger(index) ? directoryItems[index] : null;
  if (!selected) return;
  await request("/select-hea", {
    creator_id: selected.creator_id,
    hea_id: selected.hea_id,
  });
  await loadDirectory(false);
});
ui.cueCatalog.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-cue]");
  if (!button || button.disabled) return;
  const wasArmed = ui.armMotion.checked;
  const runMotion = wasArmed && button.dataset.motionEnabled === "true";
  if (wasArmed) ui.armMotion.checked = false;
  if (runMotion) {
    const confirmed = window.confirm(`Run one supervised ${button.dataset.label} movement? Keep Stop within reach.`);
    if (!confirmed) return;
  }
  await request("/preview-cue", { cue: button.dataset.cue, run_motion: runMotion });
});

async function request(path, body) {
  ui.error.hidden = true;
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `Request failed (${response.status})`);
    }
    await refresh();
  } catch (error) {
    ui.error.textContent = error.message;
    ui.error.hidden = false;
  }
}

async function refresh() {
  try {
    const response = await fetch("/state", { cache: "no-store" });
    if (!response.ok) throw new Error("Local app state unavailable");
    render(await response.json());
  } catch (error) {
    ui.appStatus.textContent = "Disconnected";
    setDot(ui.appDot, "bad");
  }
}

function render(state) {
  latestState = state;
  ui.appVersion.textContent = state.version || "unknown";
  ui.robotStatus.textContent = state.robot_ready ? "Ready" : "Not ready";
  ui.heaStatus.textContent = title(state.hea_status);
  const activeVoice = state.speech?.voice && state.speech?.language
    ? `${languageNames[state.speech.language] || state.speech.language.toUpperCase()} · ${state.speech.voice}`
    : null;
  ui.speechStatus.textContent = activeVoice || title(state.speech?.status);
  ui.appStatus.textContent = labels[state.status] || title(state.status);
  setDot(ui.robotDot, state.robot_ready ? "good" : "wait");
  setDot(ui.heaDot, state.hea_status === "ready" ? "good" : state.hea_status === "unavailable" ? "bad" : "wait");
  setDot(
    ui.speechDot,
    state.speech?.available
      ? (state.speech?.status === "degraded" ? "bad" : "good")
      : state.speech?.status === "unavailable" ? "bad" : "wait",
  );
  setDot(ui.appDot, state.status === "error" ? "bad" : state.status === "stopped" ? "stop" : state.robot_ready ? "good" : "wait");

  const directoryReady = state.directory?.status === "ready";
  const hasSelection = Boolean(state.selected_hea?.creator_id && state.selected_hea?.hea_id);
  ui.ask.disabled = state.busy || state.stopped || !state.robot_ready || !directoryReady || !hasSelection;
  ui.question.disabled = state.busy || state.stopped;
  ui.speakAnswer.disabled = state.busy || state.stopped || !state.speech?.available;
  ui.stop.disabled = state.stopped;
  ui.resume.hidden = !state.stopped;
  ui.armMotion.disabled = state.busy || state.stopped || !state.robot_ready;
  ui.heaSearch.disabled = state.busy || state.stopped || directoryState !== "ready";
  ui.heaPicker.disabled = state.busy || state.stopped || directoryState !== "ready";
  ui.refreshHeas.disabled = state.busy || directoryState === "loading";
  if (state.stopped || !state.robot_ready) ui.armMotion.checked = false;

  renderSelectedHea(state.selected_hea);
  if (state.directory?.status === "ready" && directoryState !== "ready") loadDirectory(false);

  ui.answer.textContent = state.answer || "The answer will appear here.";
  ui.answer.classList.toggle("empty", !state.answer);
  ui.requestId.textContent = state.request_id ? `request ${state.request_id}` : "";

  if (state.error) {
    ui.error.textContent = `${state.error.code}: ${state.error.message}`;
    ui.error.hidden = false;
  }

  ui.motionAllowlist.replaceChildren();
  for (const definition of state.motion_allowlist || []) {
    const item = document.createElement("span");
    item.textContent = `${definition.emoji} ${definition.label}`;
    ui.motionAllowlist.append(item);
  }

  renderCueCatalog(state);

  ui.cues.replaceChildren();
  if (!state.cues.length) {
    const item = document.createElement("li");
    item.className = "muted";
    item.textContent = "No expression cue yet.";
    ui.cues.append(item);
  } else {
    for (const cue of state.cues) {
      const item = document.createElement("li");
      const sentence = document.createElement("div");
      sentence.className = "cue-sentence";
      sentence.textContent = `${cue.emoji || (cue.speech_outcome === "spoken" ? "🔊" : "•")} ${cue.text || `Sentence ${cue.sentence_index + 1}`}`;
      const detail = document.createElement("div");
      detail.className = "cue-detail";
      const outcome = cue.outcome === "motion_disabled"
        ? "visual only · movement pending review"
        : cue.outcome === "visual_preview"
          ? "local visual preview · no movement requested"
          : cue.outcome;
      const expression = cue.cue || "no expression";
      const motion = cue.motion_cue
        ? cue.motion_cue === cue.cue
          ? outcome
          : `${outcome} via safe ${title(cue.motion_cue)} motion`
        : outcome;
      const speech = cue.speech_outcome === "spoken"
        ? `spoken${cue.speech_language ? ` in ${languageNames[cue.speech_language] || cue.speech_language.toUpperCase()}` : ""}${cue.speech_voice ? ` · ${cue.speech_voice}` : ""}`
        : cue.speech_outcome === "not_requested"
          ? "voice not requested"
          : `voice ${title(cue.speech_outcome).toLowerCase()}`;
      detail.textContent = `${expression} · sentence ${cue.sentence_index + 1} · ${speech} · ${motion}`;
      item.append(sentence, detail);
      ui.cues.append(item);
    }
  }
}

async function exportDiagnostics() {
  ui.exportDiagnostics.disabled = true;
  ui.error.hidden = true;
  try {
    const response = await fetch("/diagnostics", { cache: "no-store" });
    if (!response.ok) throw new Error(`Diagnostics unavailable (${response.status})`);
    const payload = await response.json();
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
    const href = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = `hea-reachy-mini-diagnostics-${new Date().toISOString().replaceAll(":", "-")}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(href);
  } catch (error) {
    ui.error.textContent = error.message;
    ui.error.hidden = false;
  } finally {
    ui.exportDiagnostics.disabled = false;
  }
}

async function loadDirectory(forceRefresh) {
  directoryState = "loading";
  ui.directoryStatus.textContent = "Loading directory…";
  ui.error.hidden = true;
  try {
    if (forceRefresh) {
      const refreshResponse = await fetch("/refresh-heas", { method: "POST" });
      if (!refreshResponse.ok) {
        const payload = await refreshResponse.json().catch(() => ({}));
        throw new Error(payload.detail || `Directory refresh failed (${refreshResponse.status})`);
      }
    }
    const response = await fetch("/heas", { cache: "no-store" });
    if (!response.ok) throw new Error(`Directory request failed (${response.status})`);
    const payload = await response.json();
    directoryState = payload.status || "unavailable";
    directoryItems = Array.isArray(payload.items) ? payload.items : [];
    ui.directoryStatus.textContent = directoryState === "ready"
      ? `${directoryItems.length} public HEA${directoryItems.length === 1 ? "" : "s"}`
      : title(payload.error || directoryState);
    renderDirectoryOptions(payload.selected);
  } catch (error) {
    directoryState = "unavailable";
    directoryItems = [];
    ui.directoryStatus.textContent = "Directory unavailable";
    ui.error.textContent = error.message;
    ui.error.hidden = false;
    renderDirectoryOptions();
  }
}

function renderDirectoryOptions(selectedOverride) {
  const candidate = selectedOverride || latestState?.selected_hea || null;
  const selected = candidate?.creator_id && candidate?.hea_id ? candidate : null;
  const query = String(ui.heaSearch.value || "").trim().toLowerCase();
  ui.heaPicker.replaceChildren();
  const matches = [];
  directoryItems.forEach((entry, index) => {
    const haystack = `${entry.name || ""} ${entry.creator_id || ""} ${entry.hea_id || ""}`.toLowerCase();
    if (!query || haystack.includes(query)) matches.push([entry, index]);
  });
  const selectedIsVisible = matches.some(([entry]) => Boolean(
    selected
    && entry.creator_id === selected.creator_id
    && entry.hea_id === selected.hea_id
  ));
  if (selected && !selectedIsVisible && matches.length) {
    const hiddenSelection = document.createElement("option");
    hiddenSelection.textContent = "Current selection is hidden by this search";
    hiddenSelection.value = "";
    hiddenSelection.disabled = true;
    hiddenSelection.selected = true;
    ui.heaPicker.append(hiddenSelection);
  }
  if (!matches.length) {
    const option = document.createElement("option");
    option.textContent = directoryState === "ready"
      ? selected ? "Current selection is hidden; no public HEAs match" : "No matching public HEAs"
      : "Public directory unavailable";
    option.value = "";
    ui.heaPicker.append(option);
    return;
  }
  for (const [entry, index] of matches) {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${entry.name}${entry.beta ? " · Beta" : ""}`;
    option.selected = Boolean(
      selected
      && entry.creator_id === selected.creator_id
      && entry.hea_id === selected.hea_id
    );
    ui.heaPicker.append(option);
  }
}

function renderSelectedHea(selected) {
  const name = selected?.name || "Choose a public HEA";
  ui.selectedHeaName.textContent = name;
  ui.askHeaName.textContent = name;
  ui.askButtonHeaName.textContent = name;
  ui.selectedHeaId.textContent = selected?.creator_id && selected?.hea_id
    ? `${selected.creator_id} / ${selected.hea_id}`
    : "No public HEA selected";
  const avatar = String(selected?.avatar_url || "");
  if (avatar.startsWith("https://")) {
    ui.selectedHeaAvatar.src = avatar;
    ui.selectedHeaAvatar.alt = `${name} avatar`;
    ui.selectedHeaAvatar.hidden = false;
  } else {
    ui.selectedHeaAvatar.removeAttribute("src");
    ui.selectedHeaAvatar.alt = "";
    ui.selectedHeaAvatar.hidden = true;
  }
}

function renderCueCatalog(state) {
  const catalog = state.cue_catalog || [];
  const signature = catalog.map((item) => `${item.cue}:${item.motion_enabled}`).join("|");
  if (ui.cueCatalog.dataset.signature !== signature) {
    ui.cueCatalog.replaceChildren();
    for (const definition of catalog) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = definition.motion_enabled ? "cue-chip motion-ready" : "cue-chip visual-only";
      button.dataset.cue = definition.cue;
      button.dataset.label = definition.label;
      button.dataset.motionEnabled = String(definition.motion_enabled);
      button.title = `${definition.description} ${definition.motion_enabled ? "Supervised motion is available when armed." : "Visual preview only; movement is pending review."}`;

      const emoji = document.createElement("span");
      emoji.className = "cue-chip-emoji";
      emoji.textContent = definition.emoji;
      const label = document.createElement("span");
      label.textContent = definition.label;
      const mode = document.createElement("small");
      mode.textContent = definition.motion_enabled ? "lab motion" : "visual only";
      button.append(emoji, label, mode);
      ui.cueCatalog.append(button);
    }
    ui.cueCatalog.dataset.signature = signature;
  }

  for (const button of ui.cueCatalog.querySelectorAll("button[data-cue]")) {
    button.disabled = state.busy || state.stopped || !state.robot_ready;
  }
}

function setDot(dot, state) {
  dot.className = state;
}

function title(value) {
  const text = String(value || "unknown").replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

refresh();
loadDirectory(false);
window.setInterval(refresh, 500);
