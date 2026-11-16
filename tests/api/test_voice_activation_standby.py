import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from api.interface import VoiceActivationStandbyRequest
from services.audio.listen_controller import ListenState
from wingman_core import WingmanCore


def _core(initial=False, save_result=True):
    va = SimpleNamespace(standby=initial)
    saved = []
    core = object.__new__(WingmanCore)
    core.settings_service = SimpleNamespace(
        settings=SimpleNamespace(voice_activation=va),
        save_settings_to_disk=lambda: saved.append(va.standby) or save_result,
    )
    core.get_mic_status = lambda: SimpleNamespace(standby=va.standby)
    emitted = []
    core._emit_voice_state = lambda: emitted.append(va.standby)
    return core, va, saved, emitted


def test_scoped_standby_operation_persists_only_the_requested_state():
    core, va, saved, emitted = _core()

    status = asyncio.run(
        core.update_voice_activation_standby(VoiceActivationStandbyRequest(standby=True))
    )

    assert va.standby is True
    assert saved == [True]
    assert emitted == [True]
    assert status.standby is True


def test_standby_operation_is_idempotent():
    core, va, saved, emitted = _core(initial=True)

    asyncio.run(
        core.update_voice_activation_standby(VoiceActivationStandbyRequest(standby=True))
    )

    assert va.standby is True
    assert saved == []
    assert emitted == []


def test_standby_write_failure_restores_runtime_state():
    core, va, saved, emitted = _core(save_result=False)

    with pytest.raises(OSError, match="could not persist voice standby"):
        asyncio.run(
            core.update_voice_activation_standby(
                VoiceActivationStandbyRequest(standby=True)
            )
        )

    assert va.standby is False
    assert saved == [True]
    assert emitted == []


def test_standby_request_accepts_only_a_strict_boolean():
    with pytest.raises(ValidationError):
        VoiceActivationStandbyRequest.model_validate({"standby": "true"})
    with pytest.raises(ValidationError):
        VoiceActivationStandbyRequest.model_validate(
            {"standby": True, "enabled": True}
        )


def test_status_keeps_armed_state_and_exposes_standby_separately():
    core = object.__new__(WingmanCore)
    core.listen_controller = SimpleNamespace(
        state=ListenState.ARMED, held_wingman=None, user_muted=False
    )
    core.settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            voice_activation=SimpleNamespace(enabled=True, standby=True)
        )
    )
    core.audio_player = SimpleNamespace(is_playing=False)

    status = core.get_mic_status()

    assert status.state == "armed"
    assert status.listening is True
    assert status.standby is True
