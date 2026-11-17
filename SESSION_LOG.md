# Session log

## 2026-11-17 - reaffirm Wingman UI and Computer to UEXC workflow

- Kevin clarified that the active app is the Wingman AI desktop UI backed by the Wingman Core fork. SC Companion Hub is not part of this workflow and must not be opened or modified for it.
- The requested behavior is: ask Computer for a UEX trade/market request; Computer passes the original request to UEXC; UEXC is the specialist with the UEXCorp skill and spoken activation name "UEX"; follow-up voice remains with UEXC until another Wingman is named.
- Last confirmed skill assignment: UEXCorp disabled on Computer and enabled on UEXC (live Core check, 17 Nov 2026).
- The Core worktree is `C:\Users\admin\github\wingman-ai-voice-activation`, branch `feature/voice-activation-enable`. It contains uncommitted handoff work in `services/uex_handoff.py`, `services/tool_executor.py`, `services/tower.py`, and `wingmen/wingman.py`; the app rule and task checkpoint are in `AGENTS.md` and `RESUME.md`.
- No code was changed, Core restarted, or handoff tested during this handover-only update. No commit or push was made. The handoff remains unverified end to end.
- A deterministic routing patch had been proposed earlier, but whether it was applied was not verified. Inspect current source and `git diff` before continuing.
- A later relative-path check resolved from `C:\Users\admin\github` rather than the repo and failed to read the files; it made no changes. Use absolute paths or `git -C`.

**Next action at that checkpoint:** inspect the current diff, finish deterministic routing if needed, and verify the handoff in Wingman before publishing. Superseded by the verification checkpoint below.

## 2026-11-17 - Computer speaks before UEXC handoff

- Inspected the existing local handoff implementation; the deterministic request path, UEXC forwarding, UEX activation alias, and sticky voice-routing state were already present.
- Added a spoken and displayed Computer announcement, "Passing this to UEX.", before forwarding. UEXC processing now runs as a retained background task so Computer's turn ends instead of leaving a loading placeholder while UEXC works.
- Tightened handoff-candidate matching so an unrelated question such as "what does UEX stand for?" remains with Computer; explicit trade-route, commodity, and market-data/price/lookup/search requests remain candidates.
- Added tests for handoff phrase matching, Computer's normal-question classification, UEX activation and sticky follow-ups, and the announcement occurring before UEXC processing.
- Focused checks passed: 31 pytest tests, Python compilation of the changed runtime modules, and `git diff --check`.
- Restarted Core from `C:\Users\admin\github\wingman-ai-voice-activation`; live `/ping` returned `ready`. Live `/wingman-skills` confirmed UEXCorp disabled on Computer and enabled on UEXC.
- In the native Wingman UI, sent a route request through Computer. Computer displayed "Computer is transferring this request to UEX." and "Passing this to UEX."; UEXC received the forwarded request in its own conversation, called `uex_get_trade_routes`, and returned a route response with an audio-duration indicator. Computer's loading placeholder cleared. A separate shield-generator question was answered in Computer.
- The focused routing test covers unaddressed follow-ups staying with UEXC until another Wingman is addressed. No live microphone-originated follow-up was tested. I cannot directly hear the speakers, so TTS audibility is not independently confirmed.
- Worktree remains on `feature/voice-activation-enable`, uncommitted and unpushed. No Core API schema or Wingman UI source changes were made; SC Companion Hub was not opened or modified.

**Next action:** Kevin reviews the diff and explicitly approves commit/push to `origin/feature/voice-activation-enable`. Do not merge.
