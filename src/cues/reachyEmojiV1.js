/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

export const REACHY_CUE_SET_VERSION = "reachy_emoji_v1";

export const REACHY_SUPPORTED_CUES = Object.freeze([
  {
    cue: "warm_smile",
    emoji: "😊",
    description: "Warm welcome, friendly acknowledgement, or positive social tone.",
  },
  {
    cue: "thinking",
    emoji: "🤔",
    description: "Short reflective beat before or during a thoughtful answer.",
  },
  {
    cue: "agree",
    emoji: "✅",
    description: "Confirmation, completion, or clear yes-style acknowledgement.",
  },
  {
    cue: "celebrate",
    emoji: "🎉",
    description: "Small upbeat moment for success or delight.",
  },
  {
    cue: "explain",
    emoji: "💡",
    description: "Helpful explanation, idea, or concept introduction.",
  },
  {
    cue: "listen",
    emoji: "👂",
    description: "Active listening or invite for the visitor to continue.",
  },
  {
    cue: "caution",
    emoji: "⚠️",
    description: "Careful, bounded, or safety-aware response.",
  },
  {
    cue: "goodbye",
    emoji: "👋",
    description: "Goodbye, handoff, or closing moment.",
  },
]);

const cueByEmoji = new Map(REACHY_SUPPORTED_CUES.map((item) => [item.emoji, item]));
const cueByName = new Map(REACHY_SUPPORTED_CUES.map((item) => [item.cue, item]));

export function getCueDefinition(item) {
  if (!item) return null;
  return cueByName.get(item.cue) || cueByEmoji.get(item.emoji) || null;
}

export function normalizeCueItem(item, index = 0) {
  const definition = getCueDefinition(item);

  if (!definition) {
    return null;
  }

  const rawIntensity = Number(item.intensity);
  const intensity = Number.isFinite(rawIntensity)
    ? Math.max(0, Math.min(1, rawIntensity))
    : 0.5;

  return {
    sentence_index: Number.isInteger(item.sentence_index) ? item.sentence_index : index,
    emoji: definition.emoji,
    cue: definition.cue,
    intensity,
    timing: item.timing || "during_sentence",
    reason: typeof item.reason === "string" ? item.reason : "",
  };
}

export function normalizeCuePlan(plan) {
  const items = Array.isArray(plan?.items)
    ? plan.items.map((item, index) => normalizeCueItem(item, index)).filter(Boolean)
    : [];

  return {
    type: "reachy_cue_plan",
    cue_set_version: REACHY_CUE_SET_VERSION,
    items,
  };
}
