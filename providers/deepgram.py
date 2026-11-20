"""Deepgram Aura and Flux text-to-speech provider."""

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
import websockets

from api.enums import LogType, TtsProvider
from api.interface import DeepgramTtsConfig, SoundConfig, VoiceInfo
from providers.interfaces import TtsInterface, tts_provider
from services.audio_player import AudioPlayer
from services.printr import Printr

if TYPE_CHECKING:
    from api.interface import WingmanConfig

printr = Printr()


# Deepgram's current English Aura-2 and Flux catalog. Aura-2 is served by
# /v1/speak; Flux by /v2/speak. Keep the model IDs as the selectable voice IDs
# so the OpenAI-compatible adapter can route the selected voice directly.
_AURA_2_ENGLISH_VOICES = (
    "thalia andromeda helena apollo arcas aries asteria athena atlas aurora callista "
    "cora cordelia delia draco electra harmonia hera hermes hyperion iris "
    "janus juno jupiter luna mars minerva neptune odysseus ophelia orion orpheus "
    "pandora phoebe pluto saturn selene theia vesta zeus amalthea"
).split()

_FLUX_ENGLISH_VOICES = (
    "colin alexis drew hannah kit cliff sienna cole brooke gemma haley heather "
    "miles sean bree brittany bruce conor donovan elise jack kai kelsey maeve "
    "marcelo marcus meena meghan naveen paige priya rufus sharon tanner wade wes"
).split()


def _voice_info(voice_name: str, family: str) -> VoiceInfo:
    model_id = f"{family}-{voice_name}-en"
    family_label = "Aura-2" if family == "aura-2" else "Flux"
    return VoiceInfo(
        id=model_id,
        name=f"{voice_name.title()} ({family_label})",
        locale="en",
        languages=["en"],
        provider="deepgram",
    )


@tts_provider(TtsProvider.DEEPGRAM)
class DeepgramTts(TtsInterface):
    """Synthesize speech with Deepgram's Aura Speak REST API."""

    def __init__(self, api_key: str, config: "WingmanConfig | None"):
        self._api_key = api_key
        self._config = config

    @staticmethod
    def get_available_voices() -> list[VoiceInfo]:
        """Return Deepgram's English Aura-2 and Flux voice choices."""
        return [
            *[_voice_info(name, "flux") for name in _FLUX_ENGLISH_VOICES],
            *[_voice_info(name, "aura-2") for name in _AURA_2_ENGLISH_VOICES],
        ]

    async def preview(
        self,
        text: str,
        config: DeepgramTtsConfig,
        sound_config: SoundConfig,
        audio_player: AudioPlayer,
        wingman_name: str = "system",
    ) -> None:
        await self._play(
            text=text,
            config=config,
            sound_config=sound_config,
            audio_player=audio_player,
            wingman_name=wingman_name,
        )

    async def play_audio(
        self,
        text: str,
        sound_config: SoundConfig,
        audio_player: AudioPlayer,
        wingman_name: str,
    ) -> None:
        if not text:
            return

        if self._config is None:
            printr.toast_error("Deepgram TTS is missing its Wingman configuration.")
            return

        await self._play(
            text=text,
            config=self._config.deepgram_tts,
            sound_config=sound_config,
            audio_player=audio_player,
            wingman_name=wingman_name,
        )

    async def _play(
        self,
        text: str,
        config: DeepgramTtsConfig,
        sound_config: SoundConfig,
        audio_player: AudioPlayer,
        wingman_name: str,
    ) -> None:
        if not text:
            return

        params = {
            "model": config.model,
            "encoding": "linear16",
            "container": "wav",
        }

        try:
            response = await self.request_audio(
                text=text,
                config=config,
                params=params,
            )

            await audio_player.play_with_effects(
                input_data=response.content,
                config=sound_config,
                wingman_name=wingman_name,
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            printr.toast_error(
                f"Deepgram TTS request failed ({exc.response.status_code})."
            )
            if detail:
                printr.toast_error(detail[:500])
        except httpx.RequestError as exc:
            printr.print(
                f"Deepgram TTS request failed: {exc}",
                color=LogType.WARNING,
                server_only=True,
            )
            printr.toast_error("Deepgram TTS could not reach the API.")

    async def request_audio(
        self,
        text: str,
        config: DeepgramTtsConfig,
        params: dict[str, str | int | float] | None = None,
    ) -> httpx.Response:
        """Return generated audio, for both native playback and the local API adapter."""
        if not text:
            raise ValueError("Text is required for Deepgram TTS.")

        endpoint = config.endpoint.rstrip("/")
        api_version = "v2" if config.model.startswith("flux-") else "v1"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{endpoint}/{api_version}/speak",
                params=params or {"model": config.model, "encoding": "mp3"},
                headers={
                    "Authorization": f"Token {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )
            response.raise_for_status()
            return response

    async def stream_flux_audio(
        self,
        text: str,
        config: DeepgramTtsConfig,
        params: dict[str, str | int | float] | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield Flux PCM frames from Deepgram's conversational WebSocket."""
        if not text:
            raise ValueError("Text is required for Deepgram TTS.")
        if not config.model.startswith("flux-"):
            raise ValueError("The Flux streaming endpoint requires a Flux voice.")

        endpoint = urlsplit(config.endpoint.rstrip("/"))
        if endpoint.scheme not in ("http", "https") or not endpoint.netloc:
            raise ValueError("Deepgram endpoint must be an HTTP(S) URL.")

        query_values = params or {}
        query = {
            key: query_values[key]
            for key in (
                "model",
                "encoding",
                "sample_rate",
                "speed",
                "expressivity",
                "mip_opt_out",
            )
            if key in query_values
        }
        query.setdefault("model", config.model)
        query.setdefault("encoding", "linear16")
        query.setdefault("sample_rate", 24000)
        url = urlunsplit(
            (
                "wss" if endpoint.scheme == "https" else "ws",
                endpoint.netloc,
                "/v2/speak",
                urlencode(query),
                "",
            )
        )

        async with websockets.connect(
            url,
            additional_headers={"Authorization": f"Token {self._api_key}"},
            open_timeout=10,
            close_timeout=5,
            max_size=None,
        ) as connection:
            await connection.send(json.dumps({"type": "Speak", "text": text}))
            await connection.send(json.dumps({"type": "Flush"}))

            async for message in connection:
                if isinstance(message, bytes):
                    if message:
                        yield message
                    continue

                try:
                    event = json.loads(message)
                except (TypeError, json.JSONDecodeError):
                    continue

                event_type = event.get("type") if isinstance(event, dict) else None
                if event_type == "Error":
                    code = event.get("code", "unknown")
                    raise RuntimeError(f"Deepgram Flux TTS error ({code}).")
                if event_type == "SpeechMetadata":
                    await connection.send(json.dumps({"type": "Close"}))
                elif event_type == "SessionMetadata":
                    return
