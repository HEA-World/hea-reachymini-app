---
title: Public HEAs for Reachy Mini Lite
emoji: 🤖
colorFrom: green
colorTo: yellow
sdk: static
pinned: false
license: mit
short_description: Public HEAs speaking safely through Reachy Mini Lite
tags:
  - reachy_mini
  - reachy_mini_python_app
---

# Public HEAs for Reachy Mini Lite

Store Package S public beta release candidate (app 0.6.2): choose a publicly listed HEA,
type a question, stream that HEA's normal answer, speak each completed sentence through Reachy's speaker,
show its expression cues as emoji, and translate only physically allowlisted
cues into recordings from Pollen Robotics' official Reachy Mini emotions
library.

This source prepares the public `v0.6.2-rc.1` release candidate. A clean
install from the synchronized public Space and owner physical release-candidate
test remain required before the app is promoted as a stable release.

## What it does

- uses the daemon-managed `ReachyMiniApp` lifecycle;
- reads the filtered, read-only production directory at `https://cdn.hea-world.com/heas/prod/hea_directory.json`, with a 2 MB / 1,000-row limit and local validation of identity, display text, and HTTPS avatar fields;
- keeps HEA World (`hea-world/heaguide-web-001`) selected by default when that exact identity is present in the public directory, exposes no free-form identity fields, and sends the exact selected public `creator_id` + `hea_id` to `https://hea-world.com/api/reachymini/chat`;
- starts every selected HEA with the neutral question `What do you do?`;
- renders the current browser session as a local chat transcript and keeps sentence-level speech/expression/motion outcomes in a separate **Last answer details** audit; the transcript is not persisted or sent anywhere as a second data flow;
- assigns each submitted turn a monotonic local turn id, so the new pending assistant bubble ignores the previous completed server snapshot and is updated in place throughout streaming instead of duplicating the answer;
- blocks switching during an active answer and creates fresh visitor/session identities after a real HEA change so conversation context cannot cross agents;
- disables Ask and offers an explicit retry when the public directory is unavailable or invalid; a vanished selection is cleared instead of silently falling back to another HEA;
- uses one catalog-driven, 24-cue `reachy_emoji` contract; old v1/v2 ids are accepted only for installed-client compatibility;
- takes emoji from the local catalog and displays it beside the relevant sentence without modifying the HEA answer text;
- classifies the sentence's primary communicative function instead of treating generic friendliness as `warm_smile`, while using recent cues to discourage inaccurate repetition;
- deterministically corrects a direct question misclassified as `warm_smile` or `thinking` to `listen`, while leaving an already accurate `invite` intact;
- inventories 81 official emotion recordings and maps each of the 24 canonical semantics to one of them;
- uses the Mac's offline `/usr/bin/say` service to synthesize one bounded PCM WAV per sentence, plays it through `reachy_mini.media.play_sound()`, and deletes it immediately;
- selects an installed native macOS voice from the language actually used in each sentence (including Dutch, English, French, German, Spanish, and Portuguese on the tested Mac); a known language without a matching voice fails to visible text instead of being pronounced by an English voice;
- lets the operator request an automatic, masculine, or feminine voice character. The preference is applied only among an allowlist of installed voices for the resolved sentence language; an unavailable explicit match fails to visible text instead of crossing language or silently choosing another character;
- keeps a short or label-only fragment in the current answer's confidently detected language before trusting conflicting per-sentence metadata; clear sentence text can still switch language immediately, and each new answer resets continuity;
- speaks sentences even when no expression cue is selected; local synthesis/playback failure degrades to the visible answer and existing safe motion path;
- lets the operator disable speech before a turn; Stop cancels both speaker playback and motion;
- includes a local 24-emoji lab palette: every cue can be previewed visually, while motion is off by default and requires explicit arming plus per-cue confirmation;
- keeps only four cue names movement-enabled for the supervised lab, never accepting network-provided movement values;
- renders at most one movement per two-sentence window. Positive/supportive cues may reuse the reviewed `warm_smile` recording, explanatory/listening/uncertain cues may reuse `thinking`, while confirmation and farewell retain `agree`/`goodbye`; sad, frustrated, and disagree stay motionless rather than receiving an inaccurate proxy;
- serializes motion, deduplicates sentences, applies a short hardware cooldown behind the cadence gate, and exposes a latched Stop;
- preserves the stopped state when the Reachy SDK raises during cancellation, and reports neutral-recovery failure separately without allowing cleanup to hide the original motion result;
- returns to a fixed neutral pose after playback, cancellation, failure, and shutdown;
- keeps bundled recording sounds off so the official movement never adds unrelated audio over the selected HEA's speech.
- shows app version plus answering, speaking, moving, stopped, and recoverable-error states in the local operator UI;
- writes only allowlisted JSON log metadata and offers an explicit safe-diagnostics export that excludes questions, answers, sentence text, audio, visitor/session ids, avatar URLs, and raw exceptions.

App 0.6.2 requests the canonical `reachy_emoji` contract. The production
backend still accepts hidden `reachy_emoji_v1` and `reachy_emoji_v2` aliases for
already-installed clients.

The app UI deliberately shows only the canonical emoji and semantic label.
The exact numbered recording ids below are private adapter details required by
the official dataset; they are not emoji versions and never arrive over the
network.

| HEA cue | Internal official Pollen recording |
|---|---|
| `warm_smile` | `welcoming2` |
| `thinking` | `thoughtful2` |
| `agree` | `understanding2` |
| `goodbye` | `loving1` |

Dataset: `pollen-robotics/reachy-mini-emotions-library` (Apache-2.0).
Pinned dataset revision: `873ae49f0b89114b7e535eff0c1f7560d21d9357`.

The canonical catalog is `config/reachy/reachyEmotionCatalog.json` in the
HEA-World repository. This package contains an exact checked copy at
`hea_reachy_mini/expression_catalog.json`. Pollen supplies the recordings and
descriptions; HEA-World assigns the semantic cue and Unicode emoji.

## Local validation

Use the Python bundled with Reachy Mini Control on this development Mac:

```bash
python -m unittest discover -s tests -v
node --test tests/chat_turn_state.test.js
reachy-mini-app-assistant check /absolute/path/to/hea_reachy_mini
```

For dashboard testing, install this app into Reachy Mini Control's `apps_venv`
in editable mode, then start it from the installed-app list. With the app
running, open `http://127.0.0.1:8042`.

Keep a hand near the robot and the Stop button for the first run. The Stop
route calls the SDK's `cancel_move()`, stops speaker playback, and then returns
to neutral. Reachy Mini Control also returns the robot to its default pose after
the app exits.

Spoken output is on by default and can be disabled for any turn in the local
UI. Version 0.6.2 supports speech only on the physically tested Apple-silicon
macOS/Lite setup. It validates sentence-level language metadata, checks the
actual sentence locally, and selects a matching installed macOS voice at 185 words/minute,
with a 15-second sentence cap, 45-second turn cap, 2 MB file cap, and no saved
audio. The UI shows the selected language and voice. A local detector covers
the six current HEA UI languages when the additive server field is absent;
short ambiguous sentences inherit the active answer language before conflicting
sentence metadata, while a clear detected language still switches immediately.
Other operating systems continue in visible text mode and are not part
of the current support claim.

The canonical palette does not call the selected HEA. Clicking a cue is visual-only by
default. To test one of the four supervised movements, arm one movement and
confirm that cue; the control disarms after the request. Pending cues still
return `motion_disabled` and cannot select a recording.

## Data and AI disclosure

Typed questions are sent to HEA-World and processed by the selected AI-powered
public HEA. Answer speech is synthesized offline on the local Mac, played through
Reachy's speaker, and deleted immediately. The app does not use the microphone
or camera and does not retain audio.
The local app does not require or store a credential.

The app sends the typed question, selected public `creator_id` + `hea_id`, and
fresh pseudonymous visitor/session ids to
`https://hea-world.com/api/reachymini/chat`. Public HEA avatars load only from
their validated HTTPS publication URL with no referrer. Safe diagnostics are
generated only when the operator clicks **Export safe diagnostics**; the JSON
must be reviewed before it is shared.

## Installation, removal, and support

After `v0.6.2-rc.1` is pushed to the public GitHub source repository and
`hub-sync` updates the public Hugging Face Space, Phase 4 must install this
package through Reachy Mini Control and prove update, uninstall, and reinstall
without relying on the editable development install. Public RC availability is
not a claim that the physical release gate has passed.

To stop normal use, click **Stop & neutral**, then stop the app in Reachy Mini
Control. To uninstall a released build, stop it and use the installed-app remove
control in Reachy Mini Control. Removing the app does not delete or change any
HEA-World account or public HEA.

See [SUPPORT.md](SUPPORT.md) for the safe diagnostics procedure and support
links. The app source is MIT licensed; Pollen Robotics dependencies and the
official movement library remain Apache-2.0 as recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Exact direct runtime pins are
mirrored in `constraints.txt`.

## Current limits

- Reachy Mini Lite on the owner's Apple-silicon Mac is the only intended Phase 2 target.
- Selection is limited to the current read-only public production directory. Private, shared, unlisted, draft, and revoked HEAs require a later authenticated pairing package.
- Twenty-four semantic cues are catalogued; only four official movements are currently enabled for supervised physical validation.
- Conversational cadence reuses only those four reviewed movements as disclosed semantic families; it does not execute any of the other 20 candidate recordings.
- The tested bundled SDK/daemon is 1.10.0; movement sound is deliberately disabled.
- Public app 0.6.1 is live; the 0.6.2 chat-deduplication hotfix still requires GitHub-to-Hugging-Face synchronization and a clean Reachy Mini Control update before its behavior is treated as released.
- The first HEAGuide physical turn passed answer/emoji/cooldown, but IK warnings keep motion approval open.
- Owner E6 confirms robot-speaker output, natural French/Dutch/English pronunciation, and cadence-2 movement along sentences. App 0.6.2 retains the language-continuity and voice-character behavior while preventing a previous answer snapshot from occupying a newly submitted chat bubble. Two-public-HEA selection/context isolation, Stop/neutral, 0.6.2 public update/install/uninstall, voice-character quality, voice input, and stable-release E6 remain open.
