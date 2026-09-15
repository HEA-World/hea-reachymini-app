# Phase 1 + Expression Package E + Phase 2/2c + Phase 3 execution plan

status: in progress
last_updated: 2026-09-15
owner_approval: Phase 1 received (`ok go then`); Expression Package E received (`approve Expression Package E`); Phase 2 spoken output received (`ok do that`, 2026-09-15); app 0.4.4 language-continuity hotfix received (`Approve the 0.4.4 language-continuity hotfix`, 2026-09-15); Phase 2c public-directory picker received (`yes update the doc and do it now please`, 2026-09-15); Phase 3 source hardening received (`you may have time to do Phase 3 already`, 2026-09-15)

1. Generate the package with `reachy-mini-app-assistant` and retain its entry point.
2. Implement a bounded, cancellable client for the existing HEA Reachy SSE contract.
3. Validate and deduplicate semantic cues; discard all network motion parameters.
4. Map the four Phase 1 cues to Pollen's official emotions dataset and serialize `play_move()` calls.
5. Add SDK `cancel_move()` Stop behavior, cooldowns, and neutral recovery.
6. Add the typed local UI and deterministic fake-response/fake-robot tests.
7. Run the app assistant checker before any physical movement.
8. Install through the local dashboard and perform the owner-observed one-move safety test, then the remaining Phase 1 physical cases.

Expression Package E:

1. Use one canonical `reachy_emoji` catalog with 24 cues; accept the old v1/v2 ids only as compatibility aliases.
2. Inventory the pinned 81 official emotion recordings in one canonical catalog.
3. Define 24 semantic emoji cues, each mapped to exactly one official recording.
4. Bundle an exact catalog copy in the Python app and fail deterministic checks on drift.
5. Show every accepted emotion as a locally sourced emoji beside its sentence; never parse ordinary answer emoji as motion.
6. Keep only the original four recordings movement-enabled for supervised lab validation. Enable additional recordings only after bounded physical review.
7. Validate the canonical contract in preview before publishing the app; do not create another numbered emoji family.
8. Prevent `warm_smile` collapse with primary-function routing and recent-cue context; prefer no cue to a generic smile.
9. Provide a local canonical 24-emoji lab palette that previews visually by default and requires explicit arming plus confirmation before the existing motion gate is called.

Source steps 1–9 are implemented. Physical E6 remains open because the first HEAGuide roundtrip produced correct text/emoji/cooldown but daemon IK warnings during motion. Continue with visual-only palette validation, then isolated supervised recording tests.

Phase 2 spoken output:

1. Use offline macOS `/usr/bin/say` on the only physically tested Apple-silicon/Lite platform; add no cloud TTS provider or secret.
2. Synthesize one completed sentence to a bounded temporary PCM WAV and play it through `reachy_mini.media.play_sound()`.
3. Start the permitted expression after speaker playback starts, preserve the one motion queue, and speak cue-less sentences too.
4. Keep a user-visible per-turn speech toggle. Speech failure is text-only degradation and never changes motion authorization.
5. Stop speaker playback and motion together. Delete temporary audio on completion, failure, or cancellation.
6. Validate real speaker routing, timing, Stop, and deletion with owner E6 before calling Demo Package D complete.
7. Select a native installed macOS voice from each answer sentence's language. The additive server language field and conservative local detector must agree with the actual sentence; known-language mismatches fail to visible text instead of silently using English.
8. Use cadence 2: at most one movement in each two-sentence window. Reuse only the four physically reviewed recordings as conservative semantic families, disclose the proxy in sentence status, and keep sad/frustrated/disagree visual-only.
9. Treat an SDK exception arriving after Stop as cancellation, not `local_app_error`. Neutral recovery is best-effort, emits structured metadata without user text, and never replaces the preceding motion error.
10. Preserve the current answer language for a locally ambiguous continuation before trusting conflicting per-sentence metadata. Clear detected text may still switch language, and a new turn resets continuity.

Phase 2c public HEA directory picker:

1. Read only the filtered production `hea_directory.json` already used by the website catalog; add no API, secret, login, pairing, or directory write.
2. Bound the response to 2 MB / 1,000 rows, validate exact ids and bounded display fields, accept only HTTPS avatars, deduplicate exact creator/HEA pairs, and fail closed if no valid entry remains.
3. Select HEAGuide initially only when its exact identity is present. The live 2026-09-15 directory does not contain it, so require an explicit choice rather than bypassing the public list. Expose a search + select control, never free-form identity fields.
4. Capture the selected public identity into each queued turn, reject selection/refresh while a turn is active, and disable Ask unless the current selection still belongs to a ready directory snapshot.
5. Reset both visitor and session identity after a real selection change or when the selected HEA disappears, so conversation context cannot cross HEAs.
6. Show structured retryable directory failure without logging the directory body or user text. Preserve the existing local speech, cue, motion, and Stop gates unchanged.
7. Validate two distinct public selections and context isolation through deterministic tests; owner E6 on the physical app remains required before Store Package S publication.

Source steps 1–7 are implemented in app 0.5.0. Public-directory E5 passed with 48 validated entries (the legacy HEAGuide default is absent), the official app checker passed, and 0.5.0 is installed in Reachy Mini Control without being launched. Owner physical two-HEA E6 remains open.

Phase 3 store-source hardening:

1. Freeze the public beta contract and keep microphone/camera/private/shared/unlisted HEAs out of scope.
2. Inventory and preserve both the public GitHub upstream and synchronized Hugging Face Space before replacing the legacy mock in place with a clearly labelled public RC.
3. Exact-pin the tested direct runtime dependencies and publish only the reviewed manifest.
4. Add license, third-party notices, support, AI/network/TTS/privacy disclosure, tested versions, Stop/uninstall/rollback, and honest limitations.
5. Expose the app version and all operator states; use structured text-free logs and a deliberate safe-diagnostics export.
6. Replace the placeholder Space landing page with hero media, four use steps, requirements, safety/privacy, known limits, and source/support links.
7. Prove source/package metadata, secrets boundary, unit behavior, and official clean install/entry-point/uninstall before requesting Phase 4.

Source steps 1–7 are complete locally in app 0.6.0. The reviewed manifest contains 39 files; native tests pass 65/65; the deterministic Phase 3 guardrail passes; and the official assistant passes a fresh temporary install, entry-point check, and uninstall. The canonical public repositories remain untouched until the exact staged diff is approved. Phase 4 publishes `v0.6.0-rc.1` through the existing GitHub-to-Hugging-Face sync, then performs the physical RC gate in public because the owner confirms there is no meaningful current traffic.
