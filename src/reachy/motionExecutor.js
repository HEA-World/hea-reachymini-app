/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

import { getMotionPlanForCue } from "../cues/cueToMotionMap.js";
import { normalizeCuePlan } from "../cues/reachyEmojiV1.js";

export class MotionExecutor {
  constructor({ robot, behaviorProfile = "default", onCueStart, onLog }) {
    this.robot = robot;
    this.behaviorProfile = behaviorProfile;
    this.onCueStart = onCueStart;
    this.onLog = onLog;
    this.stopped = false;
    this.lastCueAt = new Map();
  }

  setRobot(robot) {
    this.robot = robot;
  }

  setBehaviorProfile(profile) {
    this.behaviorProfile = profile || "default";
  }

  stop() {
    this.stopped = true;
    this.#sendSafePose();
  }

  async runCuePlan(cuePlan) {
    this.stopped = false;
    const normalizedPlan = normalizeCuePlan(cuePlan);

    for (const item of normalizedPlan.items) {
      if (this.stopped) break;
      await this.runCueItem(item);
    }
  }

  async runCueItem(item) {
    this.stopped = false;
    const motionPlan = getMotionPlanForCue(item, this.behaviorProfile);
    if (!motionPlan) {
      this.onLog?.(`No local motion for cue ${item.cue || item.emoji}`);
      return;
    }

    const now = Date.now();
    const lastAt = this.lastCueAt.get(motionPlan.cue) || 0;
    if (now - lastAt < motionPlan.cooldownMs) {
      this.onLog?.(`Skipped ${motionPlan.label}; still cooling down.`);
      return;
    }

    this.lastCueAt.set(motionPlan.cue, now);
    this.onLog?.(`Motion: ${motionPlan.emoji} ${motionPlan.label}`);
    this.onCueStart?.(item, motionPlan);

    for (const step of motionPlan.steps) {
      if (this.stopped) break;
      this.#applyStep(step);
      await sleep(step.holdMs);
    }
  }

  #applyStep(step) {
    if (!this.robot) {
      this.onLog?.("No Reachy robot connection; motion skipped.");
      return;
    }

    if (step.action === "head" && typeof this.robot.setHeadRpyDeg === "function") {
      this.robot.setHeadRpyDeg(step.rpy[0], step.rpy[1], step.rpy[2]);
      return;
    }

    if (step.action === "antenna" && typeof this.robot.setAntennasDeg === "function") {
      this.robot.setAntennasDeg(step.deg[0], step.deg[1]);
      return;
    }

    if (step.action === "bodyYaw" && typeof this.robot.setBodyYawDeg === "function") {
      this.robot.setBodyYawDeg(step.deg);
      return;
    }

    if (step.action === "sound" && typeof this.robot.playSound === "function") {
      this.robot.playSound(step.filename);
    }
  }

  #sendSafePose() {
    if (!this.robot) return;
    if (typeof this.robot.setHeadRpyDeg === "function") this.robot.setHeadRpyDeg(0, 0, 0);
    if (typeof this.robot.setAntennasDeg === "function") this.robot.setAntennasDeg(0, 0);
    if (typeof this.robot.setBodyYawDeg === "function") this.robot.setBodyYawDeg(0);
  }
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
