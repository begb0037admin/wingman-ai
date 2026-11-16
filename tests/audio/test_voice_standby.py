"""Soft standby gates passive transcripts and persists its wake state."""

from types import SimpleNamespace

import wingman_core
from api.interface import VoiceActivationSettings, VoiceActivationStandbyRequest
from wingman_core import _words


class _Printer:
    def print(self, *args, **kwargs):
        pass


class _Wingman:
    def __init__(self, name):
        self.config = SimpleNamespace(name=name)
        self.processed = []

    async def process(self, transcript, transcription_benchmark):
        self.processed.append(transcript)


class _Tower:
    def __init__(self):
        self.computer = _Wingman("Computer")
        self.atc = _Wingman("ATC")
        self.wingmen = [self.computer, self.atc]

    def get_addressed_wingman(self, text):
        words = _words(text)
        if words and words[0] == "computer":
            return self.computer
        if words and words[0] == "atc":
            return self.atc
        return None

    def get_wingman_from_text(self, text):
        return self.get_addressed_wingman(text)


def _core(monkeypatch, standby=True):
    va = VoiceActivationSettings(
        enabled=True, standby=standby, mute_toggle_bindings=[]
    )
    saved = []
    core = wingman_core.WingmanCore.__new__(wingman_core.WingmanCore)
    core.settings_service = SimpleNamespace(
        settings=SimpleNamespace(voice_activation=va),
        save_settings_to_disk=lambda: saved.append(va.standby) or True,
    )
    core.tower = _Tower()
    core.audio_player = SimpleNamespace(is_playing=False, speaking_text="")
    core.printr = _Printer()
    core._emit_voice_state = lambda: None
    core._run_on_main_loop = lambda coro: None

    class InlineThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(wingman_core.threading, "Thread", InlineThread)
    return core, saved


def _say(core, text, wingman=None):
    core._on_transcript(text, None, wingman, False)


def test_passive_speech_does_not_route_to_atc_or_default_in_standby(monkeypatch):
    core, _ = _core(monkeypatch)

    _say(core, "ATC, what is my heading?")
    _say(core, "what is my heading?")

    assert core.settings_service.settings.voice_activation.standby is True
    assert not core.tower.computer.processed
    assert not core.tower.atc.processed


def test_computer_alone_wakes_and_routes_to_computer_for_acknowledgement(monkeypatch):
    core, saved = _core(monkeypatch)

    _say(core, "Computer")

    assert core.settings_service.settings.voice_activation.standby is False
    assert core.tower.computer.processed == ["Computer"]
    assert not core.tower.atc.processed
    assert saved == [False]


def test_computer_request_wakes_and_routes_in_the_same_turn(monkeypatch):
    core, _ = _core(monkeypatch)

    _say(core, "Computer, show me the route")

    assert core.settings_service.settings.voice_activation.standby is False
    assert core.tower.computer.processed == ["Computer, show me the route"]


def test_stand_down_enters_standby_and_does_not_send_to_a_wingman(monkeypatch):
    core, saved = _core(monkeypatch, standby=False)

    _say(core, "stand down")

    assert core.settings_service.settings.voice_activation.standby is True
    assert saved == [True]
    assert not core.tower.computer.processed
    assert not core.tower.atc.processed


def test_okay_stand_down_enters_standby_but_questions_are_ordinary_speech(monkeypatch):
    core, saved = _core(monkeypatch, standby=False)

    _say(core, "Okay, stand down.")

    assert core.settings_service.settings.voice_activation.standby is True
    assert saved == [True]
    assert not core.tower.computer.processed

    core, _ = _core(monkeypatch, standby=True)
    _say(core, "What does stand down mean?")
    assert core.settings_service.settings.voice_activation.standby is True
    assert not core.tower.computer.processed


def test_explicit_ptt_remains_a_manual_override_without_waking(monkeypatch):
    core, _ = _core(monkeypatch)

    _say(core, "manual request", core.tower.atc)

    assert core.settings_service.settings.voice_activation.standby is True
    assert core.tower.atc.processed == ["manual request"]


def test_standby_setting_survives_settings_model_round_trip():
    settings = VoiceActivationSettings(
        enabled=True, standby=True, mute_toggle_bindings=[]
    )

    restored = VoiceActivationSettings.model_validate(settings.model_dump())

    assert restored.standby is True
    assert VoiceActivationStandbyRequest.model_validate({"standby": True}).standby
