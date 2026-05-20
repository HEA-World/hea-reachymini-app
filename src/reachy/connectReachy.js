/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

import { DEFAULT_REACHY_SDK_MODULE_URL } from "../config.js";
import { createMockReachyMini } from "./mockReachy.js";

export async function connectReachy({
  mode,
  sdkModuleUrl = DEFAULT_REACHY_SDK_MODULE_URL,
  robotId,
  videoEl,
  onLog,
  onRobotState,
  onRobotsChanged,
}) {
  const robot = mode === "reachy" ? await createRealReachy(sdkModuleUrl) : createMockReachyMini();
  const cleanupFns = bindRobotEvents(robot, { onLog, onRobotState, onRobotsChanged });

  const authenticated = await robot.authenticate();
  if (!authenticated) {
    onLog?.("Reachy SDK requested Hugging Face login.");
    robot.login();
    return { robot, connected: false, cleanup: () => cleanupFns.forEach((fn) => fn()) };
  }

  await robot.connect();

  const detachVideo = typeof robot.attachVideo === "function" && videoEl
    ? robot.attachVideo(videoEl)
    : null;

  const selectedRobotId = robotId || robot.robots?.[0]?.id || await waitForFirstRobot(robot, 2500);
  if (selectedRobotId && typeof robot.startSession === "function") {
    await robot.startSession(selectedRobotId);
    onLog?.(`Started Reachy session: ${selectedRobotId}`);
  } else {
    onLog?.("Connected to Reachy signaling. Select a robot ID to start streaming.");
  }

  return {
    robot,
    connected: true,
    cleanup: () => {
      if (typeof detachVideo === "function") detachVideo();
      cleanupFns.forEach((fn) => fn());
    },
  };
}

async function createRealReachy(sdkModuleUrl) {
  const resolvedSdkModuleUrl = sdkModuleUrl || DEFAULT_REACHY_SDK_MODULE_URL;
  let sdkModule = null;
  try {
    sdkModule = await import(resolvedSdkModuleUrl);
  } catch (error) {
    throw new Error(
      `Reachy SDK module failed to import from ${resolvedSdkModuleUrl}. ` +
      `Keep Mock robot mode enabled unless you are testing in a browser that can load the Hugging Face Reachy SDK module. ` +
      `Browser error: ${error?.message || error}`
    );
  }

  const ReachyMini = sdkModule.ReachyMini || sdkModule.default;

  if (!ReachyMini) {
    throw new Error(`Reachy SDK module did not export ReachyMini: ${resolvedSdkModuleUrl}`);
  }

  return new ReachyMini({ enableMicrophone: false });
}

function waitForFirstRobot(robot, timeoutMs) {
  return new Promise((resolve) => {
    const existingRobotId = robot.robots?.[0]?.id;
    if (existingRobotId) {
      resolve(existingRobotId);
      return;
    }

    const timeout = window.setTimeout(() => {
      cleanup();
      resolve("");
    }, timeoutMs);

    const onRobotsChanged = (event) => {
      const robotId = event.detail?.robots?.[0]?.id || "";
      if (!robotId) return;
      cleanup();
      resolve(robotId);
    };

    function cleanup() {
      window.clearTimeout(timeout);
      robot.removeEventListener("robotsChanged", onRobotsChanged);
    }

    robot.addEventListener("robotsChanged", onRobotsChanged);
  });
}

function bindRobotEvents(robot, handlers) {
  const eventNames = [
    "connected",
    "disconnected",
    "robotsChanged",
    "streaming",
    "sessionStopped",
    "state",
    "error",
    "sound",
    "raw",
  ];

  return eventNames.map((eventName) => {
    const handler = (event) => {
      if (eventName === "state") {
        handlers.onRobotState?.(event.detail);
        return;
      }

      if (eventName === "robotsChanged") {
        handlers.onRobotsChanged?.(event.detail?.robots || []);
      }

      handlers.onLog?.(`${eventName}: ${safeStringify(event.detail)}`);
    };

    robot.addEventListener(eventName, handler);
    return () => robot.removeEventListener(eventName, handler);
  });
}

function safeStringify(value) {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
