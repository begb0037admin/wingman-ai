# Wingman Core fork — Star Citizen handover for the Wingman UI

> **Current checkpoint — 17 Nov 2026. This section supersedes older “exact next action” notes below.** Use Wingman AI desktop UI + this Wingman Core fork. Do not switch to or modify SC Companion Hub for this workflow. Older Companion-specific notes later in this file are historical only.

## Active workflow rule (Kevin, 17 Nov 2026)

Use the **Wingman AI desktop UI with this Wingman Core fork**. “SC” means Star Citizen; Corps such as UEX Corp are Star Citizen features handled by Wingman/Core skills and Wingmen. SC Companion Hub is not the app for this workflow. Its repository is preserved, but do not open or use it as the UI. The SC Companion window was closed; the Wingman UI remains the active client.

## Active task: Computer hands UEX requests to UEXC

Computer must transfer UEX Corp trade, market, price, and route requests to the dedicated UEXC Wingman, whose spoken activation name is **UEX**. The original request should continue in UEXC's own Wingman conversation, and unaddressed follow-up voice turns stay with UEXC until the user says another Wingman's activation name. UEXCorp is disabled on Computer and enabled on UEXC; the live Core `/wingman-skills` endpoint confirmed these states on 17 Nov 2026.

Local changes on `feature/voice-activation-enable` now deterministically route UEX trade, commodity, market-data, price, and lookup requests from Computer to UEXC, speak and display "Passing this to UEX." before forwarding, and run UEXC's reply in its own conversation without leaving Computer's UI in a loading state. Unaddressed voice follow-ups stay with UEXC until another activation name is said. UEXCorp remains disabled on Computer and enabled on UEXC. No Wingman UI source or Core API schema changes were made.

**Verification on 17 Nov 2026:** restarted Core from this worktree; live `/ping` returned `ready`, and `/wingman-skills` confirmed Computer `UEXCorp=false`, UEXC `UEXCorp=true`. In Wingman, a request entered in Computer produced Computer's transfer notice and "Passing this to UEX." message, then UEXC's own `uex_get_trade_routes` result and response with an audio-duration indicator. A separate shield-generator question was answered in Computer. Focused tests cover the UEX alias, sticky follow-up selection, ordinary request classification, and speech-before-forward ordering: 31 passed. `py_compile` and `git diff --check` passed. No live microphone-originated follow-up was performed; sticky routing was verified by focused tests. I cannot directly hear the machine's speaker output, so TTS audibility itself is not independently confirmed.

**Exact next action:** Kevin can test a microphone-originated follow-up to UEX in Wingman; the text UI handoff and UEXC route response are verified. If that live voice test exposes an issue, continue from this branch and record the observed transcript/audio behavior. Do not merge. Do not open or use SC Companion Hub.

**Current local worktree:** the handoff changes are committed and pushed to `origin/feature/voice-activation-enable` as `16a67867` (`Add Computer to UEXC voice handoff`). The working tree was clean after that push.

## Earlier UEX route-image work: live-verified (17 Nov 2026)
- Added a UEX route-card renderer and wired it to the existing Core chat image attachment path used by Vision AI. Route searches and active-run updates post to the Wingman that owns the UEXCorp skill.
- The card shows estimated profit, capital, data age, ordered stops and actions, plus buy/sell unit prices, cargo and estimated profit. The route graphic is a stop-order schematic; UEX market values remain estimates.
- Added an **Open full size** chat link. Core stores a full-resolution 1280x960 JPEG under the UEX state folder and serves it through a loopback-only UUID route-card endpoint; clicking the link opens it in Chrome.
- Live-verified on 17 Nov: restarted Core from `feature/voice-activation-enable`, reconnected Wingman, asked UEXC for a Cutlass Black route from Area 18, observed `uex_get_vehicle_information` and `uex_get_trade_routes`, saw the route image and link in UEXC chat, and opened the image at `http://127.0.0.1:49111/uex-route-card/<id>` in Chrome. The displayed card was 1280x960. No test suite was run; `py_compile`, UEX skill import, Core startup, and `git diff --check` succeeded.
- Historical next action at the time: wait for Kevin's direction before starting another feature. Superseded by the active Computer-to-UEXC handoff task above.

## Earlier live microphone check (17 Nov 2026; historical)
- Kevin reported Computer, ATC and UEXC were not responding. The local Core status endpoint showed hands-free voice activation enabled, microphone armed and unmuted, but soft standby was on.
- Turned off soft standby through the field-scoped `/voice-activation/standby` API. A follow-up `/voice-activation/status` returned `state: armed`, `listening: true`, `muted: false`, `voice_activation_enabled: true`, `standby: false`.
- No spoken reply has been verified after this change.
- Historical next action at the time: Kevin tests a spoken request to Computer, ATC and UEXC. This is not the current task; do not change microphone or standby settings while working on the handoff.


Updated: 2026-11-17 (Europe/London). This is the `feature/voice-activation-enable` worktree at `C:\Users\admin\github\wingman-ai-voice-activation`, based on `fix/gpt-6-reasoning-none` commit `b77aa7b2bad373370f6e2389b0cff5ce97151765`. The sound selector and conversation style change are in Core commit `ba729630`.

**Historical Companion integration details below:** the `/companion/*` endpoints and Hub references record an earlier experiment. They do not make SC Companion the current app. Use the Wingman desktop UI for the active Star Citizen workflow.

## Implemented and live

- Safe field-scoped `/voice-activation/enabled` and `/voice-activation/standby` operations; status includes capability and standby fields. Standby persists in settings. Passive transcripts are ignored during standby except those addressed to Computer; `Computer` alone wakes and answers, and `Computer, [request]` wakes and routes in one utterance. `stand down` and `Okay, stand down` enter standby.
- Native-only local `/companion/initialize` and `/companion/status` operations initialise the selected Star Citizen Tower without pretending that the WingmanAI account client signed in. Requests with browser Origin or non-loopback client address are rejected. Readiness requires loaded Computer and ATC. In the earlier integration, the separate Hub initiated this after Core startup.
- Running Core was restarted with `main.py --host 127.0.0.1 --port 49111 --sidecar`; live companion status was `ready`, `Star Citizen`, Computer and ATC loaded, zero errors. Spoken `Computer` woke from standby and produced a reply; spoken `Okay, stand down` returned to standby. This records the earlier Companion integration; current UI/process checks belong to Wingman.
- Previous verification: 56 focused Core tests passed, covering voice activation, standby, companion initialization, settings round trip, transcript routing and context. No full suite was run.

## Computer voice effect selector — implemented and live

Core exposes native-only GET/PUT `/companion/computer/sound-effect`. GET returns one selected `SoundEffect` or null and the seven supported enum values. PUT accepts exactly `{"effect": enum_or_null}`; null is Natural with no processing. It backs up only Computer's file before a change, saves through ConfigService, verifies disk readback, and rolls back on failure. A pre-existing multi-effect config returns 409. The prior scoped AI-removal route remains available and shares the safe helper. Changed files: `wingman_core.py`, `api/interface.py`, new `tests/api/test_computer_ai_effect_removal.py`.

Markey ran 83 related tests, all passed; the coordinator independently ran the 25 new effect tests and 12 context-builder tests, all passed. Core was restarted with `--sidecar` and native companion initialization returned Computer and ATC ready. A verified fresh Computer-file backup preceded live PUT `{"effect": null}`; PUT reported `changed: true` and a Core backup. GET now returns null, saved Computer has no `AI` marker, and ATC's `LOW_QUALITY_RADIO` marker and file hash are unchanged. Scoped voice activation was re-enabled for the spoken test, then a final post-push live check found it off (`voice_activation_enabled: false`, `listening: false`, `standby: false`). Do not infer why it changed or turn it on without Kevin's direction.

Kevin said the voice sounds better without the effect but Computer says “Joe” too often. A targeted metadata check found that token 13 times in Computer's backstory; no raw config was displayed. `services/context_builder.py` now appends a late, Star Citizen Computer-only instruction to use the user's name sparingly in routine replies. Tests in `tests/conversation/test_context_builder.py` confirm placement and no effect on ATC/other contexts. Core was restarted with this code; companion is ready, zero initialization errors. Kevin tested spoken replies and said **“ok all good”** after the wording change.

Historical next action at the time: ask whether active listening was intentionally turned off, use the Hub hands-free control, and correct its scheduled-task launcher. Superseded for this task; do not follow these Hub-specific steps. The current task is the Computer-to-UEXC handoff through Wingman.

## Guardrails

- Use Core API operations for configuration changes; do not edit live YAML directly. Do not read `/secrets` or display raw config/settings payloads or API keys.
- Current `listen_while_speaking: false` pauses mic capture during playback. Soft standby is not hardware mic mute.
- The original Core checkout remains clean. Kevin explicitly approved the feature-branch checkpoint push by saying “go ahead” after the test result and push plan were stated. No merge or default-branch change was requested.
