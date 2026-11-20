# Wingman Core local build tracker

This ledger records repeatable local behavior baselines. IDs are tracking labels and do not change Core's product version unless a release is explicitly prepared through the project's version script.

## WC-3.2.14-20261120.03 - SC event speech loop fix

**Source:** `feature/voice-activation-enable` worktree with its existing local changes. **Product version:** 3.2.14. **Installed EXE SHA-256:** `16FD8B61E780DE2F4857303D5DB846F36A5BBDE39EBBB49FC184AB187593E06E`.

- Fixed a Core event-loop deadlock: automatic SC event speech used synchronous OpenAI-compatible TTS network reads against Core's own Deepgram adapter. The frozen `MainThread` stack was captured with `py-spy` while Star Citizen telemetry was live. Network request entry and streaming chunk reads now run in worker threads.
- Four focused tests passed: the new nonblocking TTS regression plus three existing Deepgram Flux tests. `py_compile` and `git diff --check` passed.
- Built the Core package and copied the new EXE into Program Files through an elevated step. The installed hash matches the built EXE; the old EXE is backed up at `C:\Users\admin\github\wingman-ai\_WingmanAiCore_before_event_tts_20261120.exe`. The unchanged `_internal` package is from build `.02`.
- Installed Core reached `ready` with SC telemetry `live`; `/ping` returned HTTP 200 in about 3–12 ms after startup. The source build also answered a Computer text request and completed playback under SC load. An independent WebSocket listener received Computer's user and answer chat messages. Kevin reported they were not visible in Wingman chat before the desktop client restart.
- After restarting the desktop client, display 2 visibly showed a fresh Computer chat request and reply. A later text-origin request visibly showed **Executed AI command: Open mobiGlas** and Computer's reply in Wingman chat; display 1 showed MobiGlas open in SC. MobiGlas was already open before the later command, so the remaining test is microphone-originated opening from the closed state with SC foreground. The Windows control bridge failed with `native pipe unavailable`, but Wingman's read-only screen capture module supplied both screenshots. No approved TTS voice settings were changed; no commit or push was made.
- A later paired capture did verify text-origin opening **from the closed state**: Computer's Open command appeared in chat and MobiGlas then appeared in SC. A separate microphone-originated “computer, open star map” was transcribed and executed.
- A live Computer config update added **Close mobiGlas**, using the same F1 toggle with close wording, and clarified Open's description. The close request selected Close and showed “mobiGlas is closed” in chat, but SC stayed open because Codex had focus when F1 was sent. A spoken close test with SC foreground remains open. The config backup is `C:\Users\admin\github\wingman-ai\_Computer_before_close_mobiglas_20261120.yaml`; unrelated legacy config blocks dropped by Core's full-save endpoint were restored from it and all non-command fields compared equal.
- Kevin reported missed/garbled speech. DJI Mic Mini remained the selected input and voice activation was armed/listening/unmuted. Parakeet logged the garbled transcripts “Gita” and “Close to Star map.” STT was switched through Core's API to cached local Faster-Whisper. A transcription raced model loading and errored once before Core returned to `ready`; no later spoken transcription was verified. The settings backup is `C:\Users\admin\github\wingman-ai\_settings_before_faster_whisper_20261120.yaml`; on-disk settings differ from that backup only at `stt.provider`. Deepgram voice settings were not changed. Kevin stopped testing; validate STT before claiming a voice pass.

## WC-3.2.14-20261119.01

**Core product version:** 3.2.14  
**Worktree:** `C:\Users\admin\github\wingman-ai-voice-activation`  
**Branch:** `feature/voice-activation-enable`  
**Scope:** Deepgram Flux streaming latency baseline and Computer wake recovery.

### Deepgram Flux baseline

- TTS route: Deepgram Flux PCM WebSocket streaming through Core's local OpenAI-compatible adapter.
- First audio frame: **912 ms**; complete response: **3,572 ms**.
- Batch MP3 comparison: first audio arrived at **2,349 ms** (full batch response).
- These are local API measurements, not microphone-to-speaker measurements.
- Kevin tried Wingman and confirmed: **“yes this is much better.”**
- Focused Flux tests: 3 passed. Python compilation and `git diff --check` passed.

### Computer wake recovery

- The live Core API stopped answering `/ping` and `/voice-activation/status` although the process was alive. Restarting Core from this worktree restored `/ping` to `ready`.
- Startup had no input device explicitly selected and opened the Windows default, **DJI Mic Mini headset**. Kevin clarified that he uses both DJI and BRIO and says DJI is the better mic. Core was temporarily set to BRIO (device index 2); this did not establish a device mismatch as the cause.
- Wingman exposes **Settings → Audio devices → Input Device (Mic) → Select device**. The selector was opened on the second screen and showed DJI Mic Mini, Logitech BRIO, and System default. No selection was made for Kevin. After the full PC reboot, Core again opened the Windows-default DJI mic, so the earlier BRIO selection did not survive that reboot.
- Live voice state: `armed`, `listening=true`, `muted=false`, `voice_activation_enabled=true`, `standby=false`.
- After the PC reboot, Core reached ready but logged repeated microphone input overflows starting at 21:06:52, before the Star Citizen process started at 21:09:47, and continuing afterward. Core logged a 3-second silent-stream reopen. The log records one successful spoken standby exit: “off standby computer” followed by Computer saying “Coming out of standby now” / “I’m awake.” Later Core `/ping` timed out again. WingmanAI and StarCitizen processes reported `Responding=true`, which does not prove the windows were usable. The Computer Use helper failed twice and after reinitialization, preventing visual inspection; no app/game restart was performed.
- **Not verified:** reliable wake, current standby state (status endpoint timed out), or whether the screen freeze was Wingman/Core versus Star Citizen.

### Next comparison / action

When Computer Use is available again, inspect Wingman on the second screen, check Core health, recover Core/Wingman without closing Star Citizen, then select the preferred mic and test “Computer.” Record transcript, response, and transcript-to-audio time. Keep product version 3.2.14 unless a release is intentionally prepared. No commit or push has been made; the worktree contains unrelated local changes that must be kept separate.

## WC-3.2.14-20261119.02 - installed recovery build

**Source:** feature/voice-activation-enable worktree with its current local changes. **Product version:** 3.2.14. **Built executable SHA-256:** `F87C460D7BACFE08C265B5D433685596A6812BAE02E1B2F4387B43F2CEAB4B42`.

- The package retains the GPT-6 `reasoning_effort: none` fix and the existing local Deepgram OpenAI-compatible adapter.
- Packaged Core `/ping` and `/deepgram-openai/v1/voices`: HTTP 200. Short PCM synthesis using the configured Computer, ATC and UEXC voices: HTTP 200 with nonempty audio for each.
- Installed into Program Files with Kevin's UAC approval on 20 Nov. Installer log: 3,900 files copied; installed EXE hash matches this build. Wingman was restarted against the installed sidecar. Installed `/ping` and adapter voices route returned 200; short PCM requests for Computer, ATC and UEXC returned 200 with nonempty audio. Speaker output and live spoken turns still await Kevin's check.
- Existing Computer, ATC and UEXC config values were not changed. No commit or push was made.
