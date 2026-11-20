"""A loopback TTS request must not block Core's own HTTP event loop."""

import asyncio
import threading
from types import SimpleNamespace
from time import perf_counter

from providers.open_ai import OpenAiCompatibleTts


def test_streaming_tts_yields_to_the_event_loop_during_network_reads():
    async def run():
        entered = threading.Event()
        next_read = threading.Event()

        class Response:
            def iter_bytes(self, chunk_size):
                def chunks():
                    next_read.wait(2)
                    yield b"pcm"
                return chunks()

        class Context:
            def __enter__(self):
                entered.wait(2)
                return Response()

            def __exit__(self, *_):
                return False

        class Player:
            async def stream_with_effects(self, buffer_callback, **_):
                buffer = bytearray(1024)
                assert await buffer_callback(buffer) == 3
                assert buffer[:3] == b"pcm"
                assert await buffer_callback(buffer) == 0

        tts = object.__new__(OpenAiCompatibleTts)
        tts.client = SimpleNamespace(
            audio=SimpleNamespace(
                speech=SimpleNamespace(
                    with_streaming_response=SimpleNamespace(
                        create=lambda **_: Context()
                    )
                )
            )
        )
        started = perf_counter()
        task = asyncio.create_task(
            tts.play_audio("test", "voice", "model", None, Player(), "Computer", True)
        )
        await asyncio.sleep(0.05)
        entered.set()
        await asyncio.sleep(0.05)
        next_read.set()
        await asyncio.wait_for(task, 2)
        assert perf_counter() - started < 1

    asyncio.run(run())
