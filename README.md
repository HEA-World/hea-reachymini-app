---
title: HEA Reachy Mini App Prototype
emoji: 🤖
sdk: static
pinned: false
hf_oauth: true
hf_oauth_expiration_minutes: 480
---

<!--
HEA-World Reachy Mini App Prototype
Copyright (c) 2026 HEA-World contributors
SPDX-License-Identifier: MIT
This folder is intended to be extracted into a separate open-source repository.
-->

# HEA Reachy Mini App Prototype

This folder contains the first static-browser prototype for connecting an
existing HEA-World agent to a Hugging Face Reachy Mini.

The app is intentionally light:

- it calls the future `POST /api/reachymini/chat` HEA channel API
- it consumes normal answer text plus `reachy_cue_plan` events
- it consumes `reachy_sentence_ready` events for sentence-synchronized speech and motion
- it maps cue events to local Reachy Mini motion
- it can run local thinking motion while the first sentence is still being prepared
- it can run in mock mode before the HEA API route or physical robot exists
- it shows a local expression preview so cue behavior is visible without hardware
- it isolates Reachy SDK usage in `src/reachy/connectReachy.js`

## Current Status

This is a prototype scaffold, not the final extracted open-source package.
It lives under `public/hea-reachymini-app/` so it can be served by HEA-World
now and moved to a dedicated repository later.

The intended public community home for the Hugging Face version is:

```text
https://huggingface.co/organizations/HEA-World/
```

The public sales/marketing page for the initiative is:

```text
https://hea-world.com/hea_pages/hea_reachymini.html
```

The default HEA identity is HEAGuide:

```text
creator_id = hea-world
hea_id     = heaguide-web-001
```

The default flow still keeps mock HEA responses and a mock robot enabled for
safe first-page testing. The mock robot also mirrors cue execution with a small
expression preview, so a live API response can be inspected before a physical
Reachy Mini is connected. The app now waits for sentence-ready events before
rendering the visible answer, which is the same hook a real app would use to
start TTS and movement together. Disable `Mock HEA API` to call the live
`/api/reachymini/chat` route with the prefilled HEAGuide identity.

Real Reachy Mini connection uses the official browser SDK import documented by
Hugging Face:

```js
import { ReachyMini } from "https://cdn.jsdelivr.net/npm/@anthropic-robotics/reachy-mini/+esm";
```

## Local Use

With Vercel routing, open:

```text
/reachymini/
```

If serving the `public/` folder directly without Vercel rewrites, open:

```text
/hea-reachymini-app/
```

When deployed through HEA-World Vercel, the intended public URL is:

```text
https://hea-world.com/reachymini/
```

For first tests:

1. Keep `Mock HEA API` enabled.
2. Keep `Robot mode` set to `Mock robot`.
3. Enter a question.
4. Press `Ask HEA`.

When `/api/reachymini/chat` exists, disable `Mock HEA API` and point the
endpoint field at the route.

## API Contract Expected By The App

The app sends:

```json
{
  "install_id": "optional productized install id",
  "creator_id": "optional prototype creator id",
  "hea_id": "optional prototype HEA id",
  "visitorID": "reachy-session-visitor",
  "session_id": "reachy-session-id",
  "message": "visitor text",
  "channel": "reachy_mini",
  "reachy_cue_session": true,
  "reachy_sentence_sync": true,
  "cue_set_version": "reachy_emoji_v1",
  "behavior_catalog_id": "default"
}
```

The app expects a streaming response that may include normal text deltas,
sentence-ready events, and a final backward-compatible cue plan. For robot
speech/motion sync, the preferred v1 event is:

```json
{
  "type": "reachy_sentence_ready",
  "cue_set_version": "reachy_emoji_v1",
  "sentence_index": 0,
  "text": "I am answering as a HEA through Reachy Mini.",
  "cue_item": {
    "sentence_index": 0,
    "emoji": "😊",
    "cue": "warm_smile",
    "intensity": 0.65,
    "timing": "during_sentence"
  },
  "planner_status": "ok"
}
```

The final cue plan remains available for clients that still operate in
post-answer mode:

```json
{
  "type": "reachy_cue_plan",
  "cue_set_version": "reachy_emoji_v1",
  "items": [
    {
      "sentence_index": 0,
      "emoji": "😊",
      "cue": "warm_smile",
      "intensity": 0.6,
      "timing": "during_sentence"
    }
  ]
}
```

## License

The code in this folder is MIT-licensed and marked with SPDX headers so it can
be moved into a public repository later with a clear open-source boundary.
