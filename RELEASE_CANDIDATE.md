# Store release candidate record

status: Phase 4 public-RC source staged locally; no public push performed
last_updated: 2026-09-15
app_version: 0.6.0
target_source: `https://github.com/HEA-World/hea-reachymini-app`
target_space: `https://huggingface.co/spaces/HEA-World/hea-reachymini-app`
release_tag: `v0.6.0-rc.1`

## Existing canonical release baseline

- Public GitHub upstream commit: `677c54c63b5409d16af1d5e5c16628f651374cde`
- GitHub workflow: `.github/workflows/sync-to-huggingface.yml`
- Sync direction: GitHub `main` -> Hugging Face Space through `huggingface/hub-sync`

- Visibility at inventory time: public
- SDK at inventory time: static
- Source shape: 14-file legacy browser mock; no Python package
- Baseline commit: `df9bfb88bf21bca8c0977f907b9f4880c4c4bf4c`
- Last modified: `2026-05-20T10:49:17Z`
- Space commit title: `Sync from GitHub via hub-sync`

Read-only comparison found the GitHub and Space application payloads identical;
only repository-specific metadata differs. The owner chose an in-place public
RC because there is no meaningful current traffic. Phase 4 must preserve both
baseline commits, keep the GitHub sync workflow, replace only the reviewed app
payload, label the result beta/RC, and verify the synchronized Space before any
stable-release claim.

## Frozen public beta contract

The installer can choose only a directory-listed public HEA, type a question,
hear sentence-level offline macOS speech, see any of 24 canonical emoji cues,
and receive at most one of four physically allowlisted official Pollen movement
families per two sentences. There is no microphone, camera, credential, pairing,
or private/shared/unlisted HEA access.

## Tested source baseline

- Reachy Mini Lite over USB
- Apple-silicon macOS
- Reachy Mini Control 0.9.34
- Python 3.12.14
- Reachy SDK/daemon 1.10.0
- `reachy-mini==1.10.0`
- `requests==2.34.2`

Phase 4 must prove a clean public-Space RC install, upgrade, uninstall, restart,
Stop/neutral behavior, two-HEA isolation, offline/API failures, and a bounded
physical soak. These are not inferred from Phase 3 source checks.

## Rollback

Before the RC push, retain the GitHub and Space baseline commits above and tag
the prior GitHub state. If the Python package fails install or launch, revert
the public GitHub release commit, allow `hub-sync` to restore the Space payload,
then verify the Space HEAD and reinstall the last locally validated package.
No HEA-World stored data is migrated.
