# Store release candidate record

status: Phase 4 public RC live on Hugging Face; catalog installation and owner physical validation pending
last_updated: 2026-09-15
app_version: 0.6.0
target_source: `https://github.com/HEA-World/hea-reachymini-app`
target_space: `https://huggingface.co/spaces/HEA-World/hea-reachymini-app`
release_tag: `v0.6.0-rc.1`

## Public release attempt

- GitHub release-candidate commit: `4d2fb37f713dae002ad70340478bc351086295bd`
- GitHub sync run: `34974437000` (failed before Space mutation)
- Failure: Hugging Face rejected `README.md` because `short_description` exceeded 60 characters.
- Hygiene issue found during audit: generated `build/`, `*.egg-info`, and `__pycache__` files had been staged by the release checkout.
- Repair: publish a normal follow-up commit that shortens the metadata, removes generated files, and expands `.gitignore`; do not rewrite public history.
- Space remained on baseline `df9bfb88bf21bca8c0977f907b9f4880c4c4bf4c` after the failed run.
- Corrective GitHub commit: `282b2c18bb1f6c25f9fc467f9fc1ba408b6609c6`
- Successful GitHub sync run: `34975420483`
- Synchronized Space commit: `d7a8a82c1e58391c4ba08f019b092323b936ecde`
- Payload verification: all 38 Space application files match the reviewed manifest byte-for-byte; hub-sync omits GitHub `.gitignore` and supplies Space `.gitattributes`.
- Official checker against the synchronized Space clone: metadata, clean temporary install, entry-point registration, uninstall — PASS.
- Still open: installation from Reachy Mini Control's public catalog and owner physical E6.

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

The prior GitHub state is retained on `static-prototype-archive`; the Space
baseline is recorded above. If the Python package fails install or launch,
revert the public GitHub release commits, allow `hub-sync` to restore the Space
payload, then verify the Space HEAD and reinstall the last locally validated
package. No HEA-World stored data is migrated.
