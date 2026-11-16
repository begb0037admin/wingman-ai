# Wingman Core fork — SC Companion handover

Updated: 2026-11-16 (Europe/London). This is the local `feature/voice-activation-enable` worktree at `C:\Users\admin\github\wingman-ai-voice-activation`, based on `fix/gpt-6-reasoning-none` commit `b77aa7b2bad373370f6e2389b0cff5ce97151765`. Previous feature work was pushed at `dd4160ec`; the sound selector changes are newer local work.

## Implemented and live

- Safe field-scoped `/voice-activation/enabled` and `/voice-activation/standby` operations; status includes capability and standby fields. Standby persists in settings. Passive transcripts are ignored during standby except those addressed to Computer; `Computer` alone wakes and answers, and `Computer, [request]` wakes and routes in one utterance. `stand down` and `Okay, stand down` enter standby.
- Native-only local `/companion/initialize` and `/companion/status` operations initialise the selected Star Citizen Tower without pretending that the WingmanAI account client signed in. Requests with browser Origin or non-loopback client address are rejected. Readiness requires loaded Computer and ATC. The Hub initiates this after Core startup.
- Running Core was restarted with `main.py --host 127.0.0.1 --port 49111 --sidecar`; live companion status was `ready`, `Star Citizen`, Computer and ATC loaded, zero errors. Spoken `Computer` woke from standby and produced a reply; spoken `Okay, stand down` returned to standby. See the Hub repo `RESUME.md` for the precise UI and process handover.
- Previous verification: 56 focused Core tests passed, covering voice activation, standby, companion initialization, settings round trip, transcript routing and context. No full suite was run.

## Computer voice effect selector — implemented and live

Core exposes native-only GET/PUT `/companion/computer/sound-effect`. GET returns one selected `SoundEffect` or null and the seven supported enum values. PUT accepts exactly `{"effect": enum_or_null}`; null is Natural with no processing. It backs up only Computer's file before a change, saves through ConfigService, verifies disk readback, and rolls back on failure. A pre-existing multi-effect config returns 409. The prior scoped AI-removal route remains available and shares the safe helper. Files changed locally: `wingman_core.py`, `api/interface.py`, new `tests/api/test_computer_ai_effect_removal.py`.

Markey ran 83 related tests, all passed; the coordinator independently ran the 25 new effect tests and 12 context-builder tests, all passed. Core was restarted with `--sidecar` and native companion initialization returned Computer and ATC ready. A verified fresh Computer-file backup preceded live PUT `{"effect": null}`; PUT reported `changed: true` and a Core backup. GET now returns null, saved Computer has no `AI` marker, and ATC's `LOW_QUALITY_RADIO` marker and file hash are unchanged. Scoped voice activation was re-enabled; after Kevin spoke, current status is armed/listening with standby false.

Kevin said the voice sounds better without the effect but Computer says “Joe” too often. A targeted metadata check found that token 13 times in Computer's backstory; no raw config was displayed. `services/context_builder.py` now appends a late, Star Citizen Computer-only instruction to use the user's name sparingly in routine replies. Tests in `tests/conversation/test_context_builder.py` confirm placement and no effect on ATC/other contexts. Core was restarted with this code; companion is ready, zero initialization errors. Kevin tested spoken replies and said **“ok all good”** after the wording change.

**Exact next action:** commit and push the staged API/test/style/handover change after Kevin's explicit GitHub approval. Correct the scheduled task launcher to include `--sidecar` in a separate verified step; it currently lacks the flag.

## Guardrails

- Use Core API operations for configuration changes; do not edit live YAML directly. Do not read `/secrets` or display raw config/settings payloads or API keys.
- Current `listen_while_speaking: false` pauses mic capture during playback. Soft standby is not hardware mic mute.
- The original Core checkout remains clean. Previous feature work is pushed; current selector changes are local and need Kevin's explicit approval before commit or push under his AGENTS.md.
