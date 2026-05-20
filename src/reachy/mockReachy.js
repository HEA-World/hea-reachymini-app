/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

export class MockReachyMini extends EventTarget {
  constructor() {
    super();
    this.state = "disconnected";
    this.robots = [{ id: "mock-reachy-mini", meta: { name: "Mock Reachy Mini" } }];
    this.robotState = {
      head: [0, 0, 0],
      antennas: [0, 0],
      body_yaw: 0,
      motor_mode: "enabled",
      is_move_running: false,
    };
  }

  async authenticate() {
    this.isAuthenticated = true;
    return true;
  }

  login() {
    this.dispatchEvent(new CustomEvent("error", { detail: { source: "mock", error: "login unused" } }));
  }

  async connect() {
    this.state = "connected";
    this.dispatchEvent(new CustomEvent("connected", { detail: { peerId: "mock-peer" } }));
    this.dispatchEvent(new CustomEvent("robotsChanged", { detail: { robots: this.robots } }));
  }

  async startSession(robotId = "mock-reachy-mini") {
    this.state = "streaming";
    this.dispatchEvent(new CustomEvent("streaming", { detail: { sessionId: "mock-session", robotId } }));
    this.#emitState();
  }

  async stopSession() {
    this.state = "connected";
    this.dispatchEvent(new CustomEvent("sessionStopped", { detail: { reason: "manual_stop" } }));
  }

  disconnect() {
    this.state = "disconnected";
    this.dispatchEvent(new CustomEvent("disconnected", { detail: { reason: "manual_disconnect" } }));
  }

  attachVideo() {
    return () => {};
  }

  setHeadRpyDeg(roll, pitch, yaw) {
    this.robotState.head = [roll, pitch, yaw];
    this.#emitState();
    return true;
  }

  setAntennasDeg(right, left) {
    this.robotState.antennas = [right, left];
    this.#emitState();
    return true;
  }

  setBodyYawDeg(yaw) {
    this.robotState.body_yaw = yaw;
    this.#emitState();
    return true;
  }

  playSound(filename) {
    this.dispatchEvent(new CustomEvent("sound", { detail: { filename } }));
    return true;
  }

  sendRaw(data) {
    this.dispatchEvent(new CustomEvent("raw", { detail: data }));
    return true;
  }

  requestState() {
    this.#emitState();
    return true;
  }

  #emitState() {
    this.dispatchEvent(new CustomEvent("state", { detail: { ...this.robotState } }));
  }
}

export function createMockReachyMini() {
  return new MockReachyMini();
}
