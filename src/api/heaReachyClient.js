/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

import { DEFAULT_CUE_SET_VERSION } from "../config.js";

export async function streamReachyChat({
  endpoint,
  payload,
  useMock,
  signal,
  onTextDelta,
  onCuePlan,
  onSentenceReady,
  onDone,
  onEvent,
}) {
  if (useMock) {
    return streamMockReachyChat({ payload, signal, onTextDelta, onCuePlan, onSentenceReady, onDone, onEvent });
  }

  return streamLiveReachyChat({ endpoint, payload, signal, onTextDelta, onCuePlan, onSentenceReady, onDone, onEvent });
}

async function streamLiveReachyChat({
  endpoint,
  payload,
  signal,
  onTextDelta,
  onCuePlan,
  onSentenceReady,
  onDone,
  onEvent,
}) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      Accept: "text/event-stream, application/x-ndjson, application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`HEA Reachy API failed with ${response.status}: ${detail.slice(0, 300)}`);
  }

  if (!response.body) {
    const event = await response.json();
    handleEvent(event, { onTextDelta, onCuePlan, onSentenceReady, onDone, onEvent });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    buffer = drainBuffer(buffer, (event) => handleEvent(event, {
      onTextDelta,
      onCuePlan,
      onSentenceReady,
      onDone,
      onEvent,
    }));
  }

  if (buffer.trim()) {
    drainBuffer(`${buffer}\n\n`, (event) => handleEvent(event, {
      onTextDelta,
      onCuePlan,
      onSentenceReady,
      onDone,
      onEvent,
    }));
  }
}

function drainBuffer(buffer, handleParsedEvent) {
  const sseBoundary = "\n\n";
  let boundaryIndex = buffer.indexOf(sseBoundary);

  while (boundaryIndex >= 0) {
    const frame = buffer.slice(0, boundaryIndex);
    buffer = buffer.slice(boundaryIndex + sseBoundary.length);
    parseFrame(frame).forEach(handleParsedEvent);
    boundaryIndex = buffer.indexOf(sseBoundary);
  }

  const lineBoundary = buffer.lastIndexOf("\n");
  if (lineBoundary >= 0 && !buffer.includes("data:")) {
    const chunk = buffer.slice(0, lineBoundary);
    buffer = buffer.slice(lineBoundary + 1);
    chunk.split("\n").map((line) => line.trim()).filter(Boolean).forEach((line) => {
      parseFrame(line).forEach(handleParsedEvent);
    });
  }

  return buffer;
}

function parseFrame(frame) {
  const trimmed = frame.trim();
  if (!trimmed) return [];

  const dataLines = trimmed
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());

  const payloads = dataLines.length ? dataLines : [trimmed];

  return payloads
    .filter((payload) => payload && payload !== "[DONE]")
    .map((payload) => {
      try {
        return JSON.parse(payload);
      } catch {
        return { type: "text_delta", delta: payload };
      }
    });
}

function handleEvent(event, { onTextDelta, onCuePlan, onSentenceReady, onDone, onEvent }) {
  onEvent?.(event);

  if (event.type === "reachy_sentence_ready") {
    onSentenceReady?.(event);
    return;
  }

  if (event.type === "reachy_cue_plan") {
    onCuePlan?.(event);
    return;
  }

  if (event.type === "reachy_cue_plan_failed") {
    return;
  }

  if (event.type === "reachy_done") {
    onDone?.(event);
    return;
  }

  const textDelta =
    event.delta ||
    event.text_delta ||
    event.text ||
    event.choices?.[0]?.delta?.content ||
    event.choices?.[0]?.message?.content ||
    "";

  if (textDelta) {
    onTextDelta?.(textDelta);
  }
}

async function streamMockReachyChat({
  payload,
  signal,
  onTextDelta,
  onCuePlan,
  onSentenceReady,
  onDone,
  onEvent,
}) {
  const visitorText = payload.message || "Hello";
  const sentences = [
    "I am answering as a HEA through Reachy Mini.",
    "The same HEA knowledge stays in charge; the robot receives only local behavior cues.",
    `For "${visitorText}", I would keep the answer useful, friendly, and grounded.`,
  ];
  const cueItems = [
    {
      sentence_index: 0,
      emoji: "😊",
      cue: "warm_smile",
      intensity: 0.65,
      timing: "during_sentence",
      reason: "friendly embodied opening",
    },
    {
      sentence_index: 1,
      emoji: "💡",
      cue: "explain",
      intensity: 0.55,
      timing: "during_sentence",
      reason: "explain HEA versus robot boundary",
    },
    {
      sentence_index: 2,
      emoji: "✅",
      cue: "agree",
      intensity: 0.5,
      timing: "after_sentence",
      reason: "closing confirmation",
    },
  ];

  onEvent?.({ type: "mock_start", cue_set_version: DEFAULT_CUE_SET_VERSION });

  for (let index = 0; index < sentences.length; index += 1) {
    if (signal?.aborted) return;
    await sleep(260);
    if (signal?.aborted) return;

    const delta = `${sentences[index]} `;
    onTextDelta?.(delta);
    onEvent?.({ type: "text_delta", delta });

    await sleep(180);
    if (signal?.aborted) return;
    const event = {
      type: "reachy_sentence_ready",
      cue_set_version: DEFAULT_CUE_SET_VERSION,
      sentence_index: index,
      text: sentences[index],
      cue_item: cueItems[index],
      planner_status: "mock",
    };
    onSentenceReady?.(event);
    onEvent?.(event);
  }

  const cuePlan = {
    type: "reachy_cue_plan",
    cue_set_version: DEFAULT_CUE_SET_VERSION,
    planner_status: "sentence_sync",
    sentence_count: sentences.length,
    items: cueItems,
  };

  await sleep(180);
  if (signal?.aborted) return;
  onCuePlan?.(cuePlan);
  onEvent?.(cuePlan);
  const doneEvent = { type: "reachy_done" };
  onDone?.(doneEvent);
  onEvent?.(doneEvent);
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
