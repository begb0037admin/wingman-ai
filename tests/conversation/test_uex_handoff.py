import asyncio
from types import SimpleNamespace

import wingmen.wingman as wingman_module
from services.uex_handoff import is_uex_request
from wingmen.wingman import Wingman


def test_explicit_uex_route_and_market_requests_are_handoff_candidates():
    assert is_uex_request("Computer, find me a UEX trade route")
    assert is_uex_request("UEXC, look up the commodity prices")
    assert is_uex_request("Check the UEX market data")
    assert is_uex_request("Do a UEX market lookup for gold")


def test_general_questions_remain_with_computer():
    assert not is_uex_request("Computer, how do shield generators work?")
    assert not is_uex_request("Computer, what time is it?")
    assert not is_uex_request("Computer, what does UEX stand for?")


def test_computer_speaks_before_forwarding_the_request_to_uexc(monkeypatch):
    events = []

    class FakeTarget:
        name = "UEXC"
        _unloaded = False
        config = SimpleNamespace(discoverable_skills=["UEXCorp"])
        skills = [SimpleNamespace(name="UEXCorp")]

        async def process(self, transcript):
            events.append(("process", transcript))

    target = FakeTarget()

    class FakeTower:
        def get_wingman_by_name(self, name):
            return target if name == "UEXC" else None

        def set_voice_handoff_target(self, name):
            events.append(("route", name))
            return name == "UEXC"

    class FakeConversation:
        async def add_assistant_message(self, content):
            events.append(("assistant", content))

    async def fake_print_async(text, **kwargs):
        events.append(("log", text, kwargs["color"]))

    async def fake_play_to_user(text, **kwargs):
        events.append(("speak", text, kwargs))

    async def run_transfer():
        monkeypatch.setattr(
            wingman_module, "printr", SimpleNamespace(print_async=fake_print_async)
        )
        computer = object.__new__(Wingman)
        computer.name = "Computer"
        computer.tower = FakeTower()
        computer.conversation = FakeConversation()
        computer.play_to_user = fake_play_to_user
        computer._background_tasks = set()

        result = await computer._transfer_request_to_uex(
            "Computer, find a UEX trade route from Area 18"
        )
        # Let the scheduled specialist turn begin and finish before the loop closes.
        await asyncio.gather(*computer._background_tasks)
        return result

    succeeded, message = asyncio.run(run_transfer())

    assert succeeded
    assert message == "The request was forwarded to UEX."
    assert ("assistant", "Passing this to UEX.") in events
    assert ("speak", "Passing this to UEX.", {"no_interrupt": True}) in events
    assert ("process", "find a UEX trade route from Area 18") in events
    assert events.index(("speak", "Passing this to UEX.", {"no_interrupt": True})) < events.index(
        ("process", "find a UEX trade route from Area 18")
    )
