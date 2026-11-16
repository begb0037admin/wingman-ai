# Wingman Core fork — SC Companion handover

Updated: 2026-11-16 (Europe/London). This is the local `feature/voice-activation-enable` worktree at `C:\Users\admin\github\wingman-ai-voice-activation`, based on `fix/gpt-6-reasoning-none` commit `b77aa7b2bad373370f6e2389b0cff5ce97151765`. Nothing here has been committed or pushed.

## Implemented and live

- Safe field-scoped `/voice-activation/enabled` and `/voice-activation/standby` operations; status includes capability and standby fields. Standby persists in settings. Passive transcripts are ignored during standby except those addressed to Computer; `Computer` alone wakes and answers, and `Computer, [request]` wakes and routes in one utterance. `stand down` and `Okay, stand down` enter standby.
- Native-only local `/companion/initialize` and `/companion/status` operations initialise the selected Star Citizen Tower without pretending that the WingmanAI account client signed in. Requests with browser Origin or non-loopback client address are rejected. Readiness requires loaded Computer and ATC. The Hub initiates this after Core startup.
- Running Core was restarted with `main.py --host 127.0.0.1 --port 49111 --sidecar`; live companion status was `ready`, `Star Citizen`, Computer and ATC loaded, zero errors. Spoken `Computer` woke from standby and produced a reply; spoken `Okay, stand down` returned to standby. See the Hub repo `RESUME.md` for the precise UI and process handover.
- Previous verification: 56 focused Core tests passed, covering voice activation, standby, companion initialization, settings round trip, transcript routing and context. No full suite was run.

## Unfinished Computer voice effect

The live `Star Citizen/Computer.yaml` still has `sound.effects: [AI]`; no live effect write has happened. The current worktree contains an **untested** `POST /companion/computer/ai-effect/remove` route and safe response model in `wingman_core.py` and `api/interface.py`. That patch is not loaded in the running Core. It is intended to back up Computer's config before mutation, remove only `SoundEffect.AI`, use ConfigService to update the loaded Wingman, and verify disk readback. ATC must remain unchanged.

**Exact next action:** review the endpoint's ConfigService and rollback behavior, add focused tests for native-only access, Computer-only mutation, backup-before-write, idempotence, and failed-save rollback. Run those tests with the original Core venv Python. Then make a fresh backup of the live Computer config, restart Core to load the tested endpoint, let Hub reinitialize Computer and ATC, invoke the endpoint once, verify `AI` is absent in Computer's saved effects and ATC's effects are unchanged, and have Kevin judge the next spoken Computer reply. Do not report the effect removed until that live proof.

## Guardrails

- Use Core API operations for configuration changes; do not edit live YAML directly. Do not read `/secrets` or display raw config/settings payloads or API keys.
- Current `listen_while_speaking: false` pauses mic capture during playback. Soft standby is not hardware mic mute.
- The original Core checkout remains clean. No feature-branch commit or push has been approved under Kevin's AGENTS.md.
