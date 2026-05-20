/*!
 * HEA-World Reachy Mini App Prototype
 * Copyright (c) 2026 HEA-World contributors
 * SPDX-License-Identifier: MIT
 * This file is intended to be extracted into a separate open-source repository.
 */

export const APP_VERSION = "0.1.1-prototype";

export const DEFAULT_HEA_ENDPOINT = "/api/reachymini/chat";

export const DEFAULT_HEA_PUBLIC_ENDPOINT = "https://hea-world.com/api/reachymini/chat";

export const DEFAULT_HEA_CREATOR_ID = "hea-world";

export const DEFAULT_HEA_ID = "heaguide-web-001";

export const DEFAULT_REACHY_SDK_MODULE_URL =
  "https://cdn.jsdelivr.net/npm/@anthropic-robotics/reachy-mini/+esm";

export const DEFAULT_CUE_SET_VERSION = "reachy_emoji_v1";

export function getDefaultHeaEndpoint() {
  const hostname = globalThis?.location?.hostname || "";
  if (hostname.endsWith(".hf.space") || hostname === "hf.space") {
    return DEFAULT_HEA_PUBLIC_ENDPOINT;
  }
  return DEFAULT_HEA_ENDPOINT;
}

export function makeDefaultId(prefix) {
  const randomPart = Math.random().toString(36).slice(2, 10);
  return `${prefix}_${Date.now().toString(36)}_${randomPart}`;
}
