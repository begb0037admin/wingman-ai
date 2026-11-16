import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from api.interface import MicStatusResponse, VoiceActivationEnabledRequest
from wingman_core import WingmanCore


class EventRecorder:
    def __init__(self):
        self.events = []

    async def publish(self, event_type, data):
        self.events.append((event_type, data))


class FailingEventRecorder(EventRecorder):
    def __init__(self):
        super().__init__()
        self.runtime_enabled = False

    async def publish(self, event_type, data):
        await super().publish(event_type, data)
        self.runtime_enabled = data
        if data is True:
            raise RuntimeError("event subscriber failed")


def make_core(initially_enabled=False, save=None, events=None):
    events = events or EventRecorder()
    settings = SimpleNamespace(
        voice_activation=SimpleNamespace(enabled=initially_enabled, sensitivity=0.42),
        unrelated_setting="preserve me",
    )
    saved = []

    def persist():
        saved.append(
            (
                settings.voice_activation.enabled,
                settings.voice_activation.sensitivity,
                settings.unrelated_setting,
            )
        )
        if save:
            save()
        return True

    core = object.__new__(WingmanCore)
    core.settings_service = SimpleNamespace(
        settings=settings,
        settings_events=events,
        save_settings_to_disk=persist,
    )
    core.get_mic_status = lambda: MicStatusResponse(
        state="armed" if settings.voice_activation.enabled else "off",
        listening=settings.voice_activation.enabled,
        muted=False,
        voice_activation_enabled=settings.voice_activation.enabled,
        activation_toggle_supported=True,
        playing=False,
        recording=False,
    )
    return core, events, settings, saved


def test_enable_endpoint_persists_only_enabled_then_publishes_and_returns_status():
    core, events, settings, saved = make_core()

    status = asyncio.run(
        core.update_voice_activation_enabled(VoiceActivationEnabledRequest(enabled=True))
    )

    assert settings.voice_activation.enabled is True
    assert settings.voice_activation.sensitivity == 0.42
    assert settings.unrelated_setting == "preserve me"
    assert saved == [(True, 0.42, "preserve me")]
    assert events.events == [("voice_activation_changed", True)]
    assert status == MicStatusResponse(
        state="armed",
        listening=True,
        muted=False,
        voice_activation_enabled=True,
        activation_toggle_supported=True,
        playing=False,
        recording=False,
    )


def test_enable_endpoint_is_idempotent():
    core, events, settings, saved = make_core(initially_enabled=True)

    status = asyncio.run(
        core.update_voice_activation_enabled(VoiceActivationEnabledRequest(enabled=True))
    )

    assert settings.voice_activation.enabled is True
    assert saved == []
    assert events.events == []
    assert status.voice_activation_enabled is True


def test_enable_endpoint_rolls_back_if_persistence_fails():
    def fail_save():
        raise OSError("disk unavailable")

    core, events, settings, saved = make_core(save=fail_save)

    with pytest.raises(OSError, match="disk unavailable"):
        asyncio.run(
            core.update_voice_activation_enabled(
                VoiceActivationEnabledRequest(enabled=True)
            )
        )

    assert settings.voice_activation.enabled is False
    assert saved == [(True, 0.42, "preserve me"), (False, 0.42, "preserve me")]
    assert events.events == [
        ("voice_activation_changed", True),
        ("voice_activation_changed", False),
    ]


def test_enable_endpoint_compensates_if_event_publication_fails():
    events = FailingEventRecorder()
    core, _, settings, saved = make_core(events=events)

    with pytest.raises(RuntimeError, match="event subscriber failed"):
        asyncio.run(
            core.update_voice_activation_enabled(
                VoiceActivationEnabledRequest(enabled=True)
            )
        )

    assert settings.voice_activation.enabled is False
    assert events.runtime_enabled is False
    assert events.events == [
        ("voice_activation_changed", True),
        ("voice_activation_changed", False),
    ]
    assert saved == [(False, 0.42, "preserve me")]


def test_enable_request_accepts_only_a_strict_boolean_field():
    with pytest.raises(ValidationError):
        VoiceActivationEnabledRequest.model_validate({"enabled": "true"})
    with pytest.raises(ValidationError):
        VoiceActivationEnabledRequest.model_validate(
            {"enabled": True, "api_key": "must not be accepted"}
        )
