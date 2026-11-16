import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.enums import CoreState
from api.interface import CompanionStatusResponse
import wingman_core as core_module
from wingman_core import WingmanCore


def _request(host="127.0.0.1", headers=None):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/companion/status",
        "raw_path": b"/companion/status",
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (host, 12345),
        "server": ("127.0.0.1", 49111),
    }
    return Request(scope)


def _core(state=CoreState.READY, tower=None, config_name="Star Citizen"):
    core = object.__new__(WingmanCore)
    core.core_state = state
    core.is_client_logged_in = False
    core.is_companion_authorized = False
    core.config_service = SimpleNamespace(
        current_config=SimpleNamespace(name=config_name),
        current_config_dir=SimpleNamespace(name=config_name),
    )
    core.tower = tower
    core.tower_errors = []
    return core


def test_companion_status_does_not_equate_core_ready_with_wingmen_ready():
    core = _core(tower=None)

    status = core.get_companion_status(_request())

    assert status.core_state == "ready"
    assert status.status == "not_initialized"
    assert status.wingmen_ready is False
    assert status.loaded_wingmen == []


def test_companion_status_reports_missing_configured_wingmen():
    tower = SimpleNamespace(wingmen=[SimpleNamespace(name="Computer")])
    core = _core(tower=tower)

    status = core.get_companion_status(_request())

    assert status.status == "missing_wingmen"
    assert status.wingmen_ready is False
    assert status.loaded_wingmen == ["Computer"]


def test_companion_status_reports_ready_only_with_both_wingmen():
    tower = SimpleNamespace(
        wingmen=[SimpleNamespace(name="Computer"), SimpleNamespace(name="ATC")]
    )
    core = _core(tower=tower)

    status = core.get_companion_status(_request())

    assert status.status == "ready"
    assert status.wingmen_ready is True


def test_initialize_companion_is_idempotent_when_wingmen_are_ready(monkeypatch):
    tower = SimpleNamespace(
        wingmen=[SimpleNamespace(name="Computer"), SimpleNamespace(name="ATC")]
    )
    core = _core(tower=tower)
    core._tower_lock = asyncio.Lock()
    initialized = []
    monkeypatch.setattr(core, "_initialize_tower", lambda info: initialized.append(info))

    status = asyncio.run(core.initialize_companion(_request()))

    assert status.status == "ready"
    assert initialized == []
    assert core.is_companion_authorized is False


@pytest.mark.parametrize("host", ["192.168.1.25", "10.0.0.4"])
def test_companion_endpoint_rejects_non_loopback_clients(host):
    with pytest.raises(HTTPException) as error:
        WingmanCore._require_native_companion_request(_request(host=host))
    assert error.value.status_code == 403


def test_companion_endpoint_rejects_browser_origin_even_on_loopback():
    with pytest.raises(HTTPException) as error:
        WingmanCore._require_native_companion_request(
            _request(headers={"origin": "https://example.com"})
        )
    assert error.value.status_code == 403


def test_companion_endpoint_allows_originless_loopback_native_client():
    WingmanCore._require_native_companion_request(_request(host="::1"))


def test_initialize_companion_does_not_set_account_login(monkeypatch):
    core = _core(tower=None)
    core._tower_lock = asyncio.Lock()
    monkeypatch.setattr(
        core_module,
        "ConfigWithDirInfo",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    initialized = []

    async def initialize(info):
        initialized.append(info.config_dir.name)

    monkeypatch.setattr(core, "_initialize_tower", initialize)
    status = asyncio.run(core.initialize_companion(_request("127.0.0.1")))

    assert core.is_companion_authorized is True
    assert core.is_client_logged_in is False
    assert initialized == ["Star Citizen"]
    assert isinstance(status, CompanionStatusResponse)
    assert status.wingmen_ready is False


def test_initialize_companion_does_not_load_a_different_config(monkeypatch):
    core = _core(tower=None, config_name="Other config")
    core._tower_lock = asyncio.Lock()
    monkeypatch.setattr(
        core_module,
        "ConfigWithDirInfo",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    initialized = []

    async def initialize(info):
        initialized.append(info.config_dir.name)

    monkeypatch.setattr(core, "_initialize_tower", initialize)
    status = asyncio.run(core.initialize_companion(_request()))

    assert status.status == "wrong_config"
    assert core.is_companion_authorized is False
    assert initialized == []


def test_initialize_companion_waits_until_core_is_ready(monkeypatch):
    core = _core(state=CoreState.LOADING_CONFIG, tower=None)
    core._tower_lock = asyncio.Lock()
    initialized = []

    async def initialize(info):
        initialized.append(info.config_dir.name)

    monkeypatch.setattr(core_module, "ConfigWithDirInfo", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(core, "_initialize_tower", initialize)
    status = asyncio.run(core.initialize_companion(_request()))

    assert status.status == "core_not_ready"
    assert core.is_companion_authorized is False
    assert initialized == []
