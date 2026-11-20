"""Flux TTS audio is relayed over the live WebSocket transport."""

import asyncio
import json
from unittest.mock import patch

from fastapi.responses import StreamingResponse

from api.interface import DeepgramTtsConfig
from providers.deepgram import DeepgramTts
from services.voice_service import VoiceService


class FakeConnection:
    def __init__(self):
        self.sent = []
        self.messages = iter(
            [
                json.dumps({"type": "Connected"}),
                json.dumps({"type": "SpeechStarted", "speech_id": "test"}),
                b"first pcm frame",
                b"second pcm frame",
                json.dumps({"type": "SpeechMetadata", "audio_duration_ms": 100}),
            ]
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def send(self, message):
        self.sent.append(message)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration


def test_flux_stream_sends_speak_and_flush_then_yields_audio_frames():
    async def run():
        connection = FakeConnection()
        with patch(
            "providers.deepgram.websockets.connect", return_value=connection
        ) as connect:
            provider = DeepgramTts(api_key="test-key", config=None)
            chunks = [
                chunk
                async for chunk in provider.stream_flux_audio(
                    "A quick reply.",
                    DeepgramTtsConfig(model="flux-colin-en"),
                    params={
                        "model": "flux-colin-en",
                        "encoding": "linear16",
                        "sample_rate": 24000,
                        "container": "none",
                        "speed": 1.0,
                    },
                )
            ]

        url = connect.call_args.args[0]
        headers = connect.call_args.kwargs["additional_headers"]
        return chunks, connection.sent, url, headers

    chunks, sent, url, headers = asyncio.run(run())

    assert chunks == [b"first pcm frame", b"second pcm frame"]
    assert [json.loads(message)["type"] for message in sent] == [
        "Speak",
        "Flush",
        "Close",
    ]
    assert json.loads(sent[0])["text"] == "A quick reply."
    assert url == (
        "wss://api.eu.deepgram.com/v2/speak?model=flux-colin-en"
        "&encoding=linear16&sample_rate=24000&speed=1.0"
    )
    assert headers == {"Authorization": "Token test-key"}


def test_flux_stream_rejects_aura_voice():
    async def run():
        provider = DeepgramTts(api_key="test-key", config=None)
        try:
            async for _ in provider.stream_flux_audio(
                "Hello.", DeepgramTtsConfig(model="aura-2-thalia-en")
            ):
                pass
        except ValueError as exc:
            return str(exc)
        raise AssertionError("Aura voice was accepted by the Flux endpoint")

    assert asyncio.run(run()) == "The Flux streaming endpoint requires a Flux voice."


def test_compatible_flux_endpoint_relays_pcm_as_a_stream():
    async def run():
        connection = FakeConnection()
        service = object.__new__(VoiceService)
        service.secret_keeper = type(
            "Secrets", (), {"secrets": {"deepgram": "test-key"}}
        )()
        service.printr = type("PrintrStub", (), {"print": lambda *args, **kwargs: None})()
        request = type(
            "RequestStub", (), {"client": type("Client", (), {"host": "127.0.0.1"})()}
        )()
        payload = {
            "input": "A quick reply.",
            "voice": "flux-colin-en",
            "model": "flux-colin-en",
            "response_format": "pcm",
            "speed": 1.0,
        }

        with patch(
            "providers.deepgram.websockets.connect", return_value=connection
        ):
            response = await service.synthesize_deepgram_compatible(request, payload)
            chunks = [chunk async for chunk in response.body_iterator]

        return response, chunks, connection.sent

    response, chunks, sent = asyncio.run(run())

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "audio/pcm"
    assert chunks == [b"first pcm frame", b"second pcm frame"]
    assert [json.loads(message)["type"] for message in sent] == [
        "Speak",
        "Flush",
        "Close",
    ]
