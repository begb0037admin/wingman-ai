import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.enums import SoundEffect
from api.interface import ComputerSoundEffectSelectionRequest
from pydantic import ValidationError
from wingman_core import WingmanCore


def _request(host="127.0.0.1", origin=None):
    headers = [(b"origin", origin.encode())] if origin else []
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/companion/computer/ai-effect/remove",
            "headers": headers,
            "client": (host, 12345),
            "server": ("127.0.0.1", 49111),
        }
    )


def _core(tmp_path, *, effects=None, save_mode="success", config_name="Star Citizen"):
    effects = effects if effects is not None else [SoundEffect.AI, SoundEffect.INTERIOR_SMALL]
    config_folder = tmp_path / config_name
    config_folder.mkdir()
    config_path = config_folder / "Computer.yaml"
    config_path.write_text("before", encoding="utf-8")
    atc_path = config_folder / "ATC.yaml"
    atc_path.write_text("atc unchanged", encoding="utf-8")
    config_dir = SimpleNamespace(name=config_name, directory=config_name)
    computer_file = SimpleNamespace(name="Computer", file="Computer.yaml")
    saved = []
    updated = []
    persisted_effects = list(effects)

    async def update_config(config):
        updated.append(list(config.sound.effects))
        return True

    computer = SimpleNamespace(name="Computer", update_config=update_config)
    tower = SimpleNamespace(get_wingman_by_name=lambda name: computer if name == "Computer" else None)

    def load_wingman_config(_config_dir, _computer_file):
        assert _computer_file.name == "Computer"
        if config_path.read_text(encoding="utf-8") == "after":
            return SimpleNamespace(sound=SimpleNamespace(effects=list(persisted_effects)))
        return SimpleNamespace(sound=SimpleNamespace(effects=list(effects)))

    config_manager = SimpleNamespace(
        config_dir=str(tmp_path),
        get_wingmen_configs=lambda _dir: [computer_file, SimpleNamespace(name="ATC", file="ATC.yaml")],
        load_wingman_config=load_wingman_config,
    )

    async def save_wingman_config(**kwargs):
        assert kwargs["wingman_file"].name == "Computer"
        saved.append(kwargs)
        backups = list(Path(tmp_path / config_name).glob("Computer.yaml.before-*.bak"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "before"
        await computer.update_config(kwargs["wingman_config"])
        if save_mode == "raise_after_write":
            config_path.write_text("broken", encoding="utf-8")
            raise OSError("simulated save failure")
        if save_mode == "false":
            return False
        if save_mode == "unconfirmed":
            return True
        persisted_effects[:] = list(kwargs["wingman_config"].sound.effects)
        config_path.write_text("after", encoding="utf-8")
        return True

    core = object.__new__(WingmanCore)
    core.config_service = SimpleNamespace(
        current_config_dir=config_dir,
        config_manager=config_manager,
        save_wingman_config=save_wingman_config,
    )
    core.tower = tower
    return core, config_path, saved, updated


@pytest.mark.parametrize("companion_request", [_request(host="192.168.1.10"), _request(origin="https://example.com")])
def test_removal_rejects_non_native_requests_before_accessing_config(tmp_path, companion_request):
    core, config_path, saved, _ = _core(tmp_path)

    with pytest.raises(HTTPException) as error:
        asyncio.run(core.remove_computer_ai_effect(companion_request))

    assert error.value.status_code == 403
    assert saved == []
    assert config_path.read_text(encoding="utf-8") == "before"


def test_removal_requires_active_star_citizen_config(tmp_path):
    core, config_path, saved, _ = _core(tmp_path, config_name="Other")

    with pytest.raises(HTTPException) as error:
        asyncio.run(core.remove_computer_ai_effect(_request()))

    assert error.value.status_code == 409
    assert saved == []
    assert config_path.read_text(encoding="utf-8") == "before"


def test_removal_backs_up_original_and_changes_only_computer_effects(tmp_path):
    core, config_path, saved, updated = _core(tmp_path)

    result = asyncio.run(core.remove_computer_ai_effect(_request()))

    backups = list(config_path.parent.glob("Computer.yaml.before-ai-effect-removal-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "before"
    assert len(saved) == 1
    assert saved[0]["wingman_file"].name == "Computer"
    assert saved[0]["wingman_config"].sound.effects == [SoundEffect.INTERIOR_SMALL]
    assert updated == [[SoundEffect.INTERIOR_SMALL]]
    assert result.changed is True
    assert result.removed_effects == ["AI"]
    assert result.remaining_effects == ["INTERIOR_SMALL"]
    assert result.backup_file == backups[0].name


def test_removal_is_idempotent_without_writing_or_backing_up(tmp_path):
    core, config_path, saved, _ = _core(tmp_path, effects=[SoundEffect.INTERIOR_SMALL])

    result = asyncio.run(core.remove_computer_ai_effect(_request()))

    assert result.changed is False
    assert result.remaining_effects == ["INTERIOR_SMALL"]
    assert saved == []
    assert list(config_path.parent.glob("*.bak")) == []


@pytest.mark.parametrize("save_mode", ["false", "raise_after_write", "unconfirmed"])
def test_failed_save_restores_file_and_loaded_computer(tmp_path, save_mode):
    core, config_path, saved, updated = _core(tmp_path, save_mode=save_mode)
    original = config_path.read_bytes()

    with pytest.raises(HTTPException) as error:
        asyncio.run(core.remove_computer_ai_effect(_request()))

    assert error.value.status_code == 500
    assert len(saved) == 1
    assert config_path.read_bytes() == original
    assert updated[-1] == [SoundEffect.AI, SoundEffect.INTERIOR_SMALL]


def test_selector_request_requires_one_supported_choice_or_null():
    assert ComputerSoundEffectSelectionRequest.model_validate({"effect": None}).effect is None
    assert ComputerSoundEffectSelectionRequest.model_validate({"effect": "AI"}).effect == SoundEffect.AI
    for invalid in ({}, {"effect": "ECHO"}, {"effect": None, "name": "ATC"}):
        with pytest.raises(ValidationError):
            ComputerSoundEffectSelectionRequest.model_validate(invalid)


@pytest.mark.parametrize(
    "effects,expected",
    [([], None), ([SoundEffect.AI], SoundEffect.AI)],
)
def test_selector_get_returns_current_choice_and_catalogue(tmp_path, effects, expected):
    core, _, _, _ = _core(tmp_path, effects=effects)

    result = core.get_computer_sound_effect(_request())

    assert result.effect == expected
    assert result.available_effects == list(SoundEffect)
    assert result.changed is False


@pytest.mark.parametrize("effect", [None, *SoundEffect])
def test_selector_put_round_trips_each_choice_and_preserves_atc(tmp_path, effect):
    core, config_path, saved, updated = _core(tmp_path, effects=[SoundEffect.AI])
    atc_path = config_path.parent / "ATC.yaml"
    atc_original = atc_path.read_bytes()
    choice = ComputerSoundEffectSelectionRequest(effect=effect)

    result = asyncio.run(core.set_computer_sound_effect(_request(), choice))

    expected = [] if effect is None else [effect]
    assert result.effect == effect
    assert result.available_effects == list(SoundEffect)
    assert len(saved) == (0 if effect == SoundEffect.AI else 1)
    assert atc_path.read_bytes() == atc_original
    if effect != SoundEffect.AI:
        assert updated == [expected]
        assert saved[0]["wingman_config"].sound.effects == expected
        backups = list(config_path.parent.glob("Computer.yaml.before-sound-effect-selection-*.bak"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "before"
        assert result.changed is True
        assert result.backup_file == backups[0].name
    else:
        assert result.changed is False
        assert result.backup_file is None


@pytest.mark.parametrize("save_mode", ["false", "raise_after_write", "unconfirmed"])
def test_selector_failed_save_rolls_back_file_and_runtime(tmp_path, save_mode):
    core, config_path, saved, updated = _core(
        tmp_path, effects=[SoundEffect.AI], save_mode=save_mode
    )
    original = config_path.read_bytes()

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            core.set_computer_sound_effect(
                _request(), ComputerSoundEffectSelectionRequest(effect=None)
            )
        )

    assert error.value.status_code == 500
    assert len(saved) == 1
    assert config_path.read_bytes() == original
    assert updated[-1] == [SoundEffect.AI]


@pytest.mark.parametrize("operation", ["get", "put"])
def test_selector_rejects_browser_origin_before_config_access(tmp_path, operation):
    core, config_path, saved, _ = _core(tmp_path)
    request = _request(origin="https://example.com")

    with pytest.raises(HTTPException) as error:
        if operation == "get":
            core.get_computer_sound_effect(request)
        else:
            asyncio.run(
                core.set_computer_sound_effect(
                    request, ComputerSoundEffectSelectionRequest(effect=None)
                )
            )

    assert error.value.status_code == 403
    assert saved == []
    assert config_path.read_text(encoding="utf-8") == "before"


def test_selector_rejects_existing_stacked_effects(tmp_path):
    core, config_path, saved, _ = _core(
        tmp_path, effects=[SoundEffect.AI, SoundEffect.INTERIOR_SMALL]
    )

    with pytest.raises(HTTPException) as get_error:
        core.get_computer_sound_effect(_request())
    with pytest.raises(HTTPException) as put_error:
        asyncio.run(
            core.set_computer_sound_effect(
                _request(), ComputerSoundEffectSelectionRequest(effect=None)
            )
        )

    assert get_error.value.status_code == put_error.value.status_code == 409
    assert saved == []
    assert config_path.read_text(encoding="utf-8") == "before"
