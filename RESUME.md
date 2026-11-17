# Wingman Core fork — SC Companion handover

## UEX route images and full-size link: live-verified (17 Nov 2026)
- Added a UEX route-card renderer and wired it to the existing Core chat image attachment path used by Vision AI. Route searches and active-run updates post to the Wingman that owns the UEXCorp skill.
- The card shows estimated profit, capital, data age, ordered stops and actions, plus buy/sell unit prices, cargo and estimated profit. The route graphic is a stop-order schematic; UEX market values remain estimates.
- Added an **Open full size** chat link. Core stores a full-resolution 1280x960 JPEG under the UEX state folder and serves it through a loopback-only UUID route-card endpoint; clicking the link opens it in Chrome.
- Live-verified on 17 Nov: restarted Core from `feature/voice-activation-enable`, reconnected Wingman, asked UEXC for a Cutlass Black route from Area 18, observed `uex_get_vehicle_information` and `uex_get_trade_routes`, saw the route image and link in UEXC chat, and opened the image at `http://127.0.0.1:49111/uex-route-card/<id>` in Chrome. The displayed card was 1280x960. No test suite was run; `py_compile`, UEX skill import, Core startup, and `git diff --check` succeeded.
- **Exact next action:** commit and push this reviewed feature-branch checkpoint with Kevin's approval. Afterward, wait for Kevin's direction before starting the next feature. Do not merge.


Updated: 2026-11-17 (Europe/London). This is the `feature/voice-activation-enable` worktree at `C:\Users\admin\github\wingman-ai-voice-activation`, based on `fix/gpt-6-reasoning-none` commit `b77aa7b2bad373370f6e2389b0cff5ce97151765`. The sound selector and conversation style change are in Core commit `ba729630`; Hub selector is in `8001d97`.

## Implemented and live

- Safe field-scoped `/voice-activation/enabled` and `/voice-activation/standby` operations; status includes capability and standby fields. Standby persists in settings. Passive transcripts are ignored during standby except those addressed to Computer; `Computer` alone wakes and answers, and `Computer, [request]` wakes and routes in one utterance. `stand down` and `Okay, stand down` enter standby.
- Native-only local `/companion/initialize` and `/companion/status` operations initialise the selected Star Citizen Tower without pretending that the WingmanAI account client signed in. Requests with browser Origin or non-loopback client address are rejected. Readiness requires loaded Computer and ATC. The Hub initiates this after Core startup.
- Running Core was restarted with `main.py --host 127.0.0.1 --port 49111 --sidecar`; live companion status was `ready`, `Star Citizen`, Computer and ATC loaded, zero errors. Spoken `Computer` woke from standby and produced a reply; spoken `Okay, stand down` returned to standby. See the Hub repo `RESUME.md` for the precise UI and process handover.
- Previous verification: 56 focused Core tests passed, covering voice activation, standby, companion initialization, settings round trip, transcript routing and context. No full suite was run.

## Computer voice effect selector — implemented and live

Core exposes native-only GET/PUT `/companion/computer/sound-effect`. GET returns one selected `SoundEffect` or null and the seven supported enum values. PUT accepts exactly `{"effect": enum_or_null}`; null is Natural with no processing. It backs up only Computer's file before a change, saves through ConfigService, verifies disk readback, and rolls back on failure. A pre-existing multi-effect config returns 409. The prior scoped AI-removal route remains available and shares the safe helper. Changed files: `wingman_core.py`, `api/interface.py`, new `tests/api/test_computer_ai_effect_removal.py`.

Markey ran 83 related tests, all passed; the coordinator independently ran the 25 new effect tests and 12 context-builder tests, all passed. Core was restarted with `--sidecar` and native companion initialization returned Computer and ATC ready. A verified fresh Computer-file backup preceded live PUT `{"effect": null}`; PUT reported `changed: true` and a Core backup. GET now returns null, saved Computer has no `AI` marker, and ATC's `LOW_QUALITY_RADIO` marker and file hash are unchanged. Scoped voice activation was re-enabled for the spoken test, then a final post-push live check found it off (`voice_activation_enabled: false`, `listening: false`, `standby: false`). Do not infer why it changed or turn it on without Kevin's direction.

Kevin said the voice sounds better without the effect but Computer says “Joe” too often. A targeted metadata check found that token 13 times in Computer's backstory; no raw config was displayed. `services/context_builder.py` now appends a late, Star Citizen Computer-only instruction to use the user's name sparingly in routine replies. Tests in `tests/conversation/test_context_builder.py` confirm placement and no effect on ATC/other contexts. Core was restarted with this code; companion is ready, zero initialization errors. Kevin tested spoken replies and said **“ok all good”** after the wording change.

**Exact next action:** ask Kevin whether he intentionally turned active listening off; if he wants it on, use the Hub's Hands-free listening control. Correct the scheduled task launcher to include `--sidecar` in a separate verified step; it currently lacks the flag. Then test a controlled automatic start, Companion readiness and the taskbar status window on monitor two.

## Guardrails

- Use Core API operations for configuration changes; do not edit live YAML directly. Do not read `/secrets` or display raw config/settings payloads or API keys.
- Current `listen_while_speaking: false` pauses mic capture during playback. Soft standby is not hardware mic mute.
- The original Core checkout remains clean. Kevin explicitly approved the feature-branch checkpoint push by saying “go ahead” after the test result and push plan were stated. No merge or default-branch change was requested.
