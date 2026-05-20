/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

import { getCueDefinition } from "./reachyEmojiV1.js";

export const BEHAVIOR_PROFILES = Object.freeze({
  default: { amplitude: 1, duration: 1, label: "Default" },
  calm: { amplitude: 0.65, duration: 1.15, label: "Calm" },
  showroom: { amplitude: 1.25, duration: 0.9, label: "Showroom" },
  reduced_motion: { amplitude: 0.35, duration: 1.25, label: "Reduced motion" },
});

const BASE_MOTIONS = Object.freeze({
  warm_smile: {
    label: "Warm smile",
    cooldownMs: 1200,
    steps: [
      { action: "head", rpy: [0, 6, 0], holdMs: 260 },
      { action: "antenna", deg: [12, -12], holdMs: 320 },
      { action: "head", rpy: [0, 0, 0], holdMs: 260 },
      { action: "antenna", deg: [0, 0], holdMs: 220 },
    ],
  },
  thinking: {
    label: "Thinking beat",
    cooldownMs: 1600,
    steps: [
      { action: "head", rpy: [0, -4, -8], holdMs: 360 },
      { action: "antenna", deg: [-8, -2], holdMs: 300 },
      { action: "head", rpy: [0, 0, 0], holdMs: 260 },
      { action: "antenna", deg: [0, 0], holdMs: 220 },
    ],
  },
  agree: {
    label: "Small nod",
    cooldownMs: 1000,
    steps: [
      { action: "head", rpy: [0, 8, 0], holdMs: 180 },
      { action: "head", rpy: [0, -2, 0], holdMs: 160 },
      { action: "head", rpy: [0, 0, 0], holdMs: 220 },
    ],
  },
  celebrate: {
    label: "Tiny celebration",
    cooldownMs: 1800,
    steps: [
      { action: "antenna", deg: [24, -24], holdMs: 180 },
      { action: "bodyYaw", deg: 8, holdMs: 180 },
      { action: "bodyYaw", deg: -8, holdMs: 180 },
      { action: "bodyYaw", deg: 0, holdMs: 180 },
      { action: "antenna", deg: [0, 0], holdMs: 220 },
    ],
  },
  explain: {
    label: "Helpful explain",
    cooldownMs: 1300,
    steps: [
      { action: "head", rpy: [0, 2, 8], holdMs: 280 },
      { action: "antenna", deg: [10, 6], holdMs: 260 },
      { action: "head", rpy: [0, 2, -6], holdMs: 260 },
      { action: "head", rpy: [0, 0, 0], holdMs: 220 },
      { action: "antenna", deg: [0, 0], holdMs: 220 },
    ],
  },
  listen: {
    label: "Listening pose",
    cooldownMs: 1200,
    steps: [
      { action: "head", rpy: [0, -3, 5], holdMs: 520 },
      { action: "antenna", deg: [4, 10], holdMs: 320 },
      { action: "head", rpy: [0, 0, 0], holdMs: 220 },
      { action: "antenna", deg: [0, 0], holdMs: 220 },
    ],
  },
  caution: {
    label: "Careful beat",
    cooldownMs: 1700,
    steps: [
      { action: "head", rpy: [0, -6, 0], holdMs: 480 },
      { action: "antenna", deg: [-8, -8], holdMs: 340 },
      { action: "head", rpy: [0, 0, 0], holdMs: 240 },
      { action: "antenna", deg: [0, 0], holdMs: 220 },
    ],
  },
  goodbye: {
    label: "Goodbye",
    cooldownMs: 1800,
    steps: [
      { action: "bodyYaw", deg: 7, holdMs: 180 },
      { action: "bodyYaw", deg: -7, holdMs: 180 },
      { action: "bodyYaw", deg: 6, holdMs: 180 },
      { action: "bodyYaw", deg: 0, holdMs: 180 },
      { action: "antenna", deg: [14, -14], holdMs: 260 },
      { action: "antenna", deg: [0, 0], holdMs: 220 },
    ],
  },
});

export function getMotionPlanForCue(item, profileName = "default") {
  const cueDefinition = getCueDefinition(item);
  const cueName = cueDefinition?.cue;
  const base = BASE_MOTIONS[cueName];

  if (!base) {
    return null;
  }

  const profile = BEHAVIOR_PROFILES[profileName] || BEHAVIOR_PROFILES.default;
  const intensity = Number.isFinite(item.intensity) ? item.intensity : 0.5;
  const amplitudeScale = profile.amplitude * (0.5 + intensity * 0.7);
  const durationScale = profile.duration;

  return {
    cue: cueName,
    emoji: cueDefinition.emoji,
    label: base.label,
    cooldownMs: Math.round(base.cooldownMs * durationScale),
    steps: base.steps.map((step) => scaleStep(step, amplitudeScale, durationScale)),
  };
}

function scaleStep(step, amplitudeScale, durationScale) {
  const scaled = { ...step, holdMs: Math.round(step.holdMs * durationScale) };

  if (Array.isArray(step.rpy)) {
    scaled.rpy = step.rpy.map((value) => round(value * amplitudeScale));
  }

  if (Array.isArray(step.deg)) {
    scaled.deg = step.deg.map((value) => round(value * amplitudeScale));
  }

  if (typeof step.deg === "number") {
    scaled.deg = round(step.deg * amplitudeScale);
  }

  return scaled;
}

function round(value) {
  return Math.round(value * 10) / 10;
}
