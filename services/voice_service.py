import asyncio
import ipaddress
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
import httpx
from api.enums import LogType, TtsProvider
from api.interface import (
    AzureTtsConfig,
    EdgeTtsConfig,
    DeepgramTtsConfig,
    ElevenlabsConfig,
    HumeConfig,
    InworldConfig,
    SoundConfig,
    VoiceInfo,
    XVASynthTtsConfig,
    PocketTTSConfig,
)
from providers.edge import Edge, get_edge_voices
from providers.deepgram import DeepgramTts
from providers.elevenlabs import ElevenLabs
from providers.hume import Hume
from providers.inworld import Inworld
from providers.open_ai import OpenAi, OpenAiCompatibleTts
from providers.wingman_subscription import WingmanSubscription
from providers.xvasynth import XVASynth
from providers.pocket_tts import PocketTTS

from services.audio_player import AudioPlayer
from services import speech_text
from services.config_manager import ConfigManager
from services.printr import Printr
from services.secret_keeper import SecretKeeper
from services.spoken_language import elevenlabs_language, inworld_language


class VoiceService:
    def __init__(
        self,
        config_manager: ConfigManager,
        audio_player: AudioPlayer,
        xvasynth: XVASynth,
        pocket_tts: PocketTTS,
        secret_keeper: SecretKeeper,
    ):
        self.printr = Printr()
        self.config_manager = config_manager
        self.audio_player = audio_player
        self.xvasynth = xvasynth
        self.pocket_tts = pocket_tts
        self.secret_keeper = secret_keeper
        self.edge_voices: list[VoiceInfo] = []

        self.router = APIRouter()
        tags = ["voice"]
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/elevenlabs",
            endpoint=self.get_elevenlabs_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/hume",
            endpoint=self.get_hume_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/inworld",
            endpoint=self.get_inworld_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/edge",
            endpoint=self.get_edge_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/deepgram",
            endpoint=self.get_deepgram_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/openai-compatible",
            endpoint=self.get_openai_compatible_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/azure/wingman-pro",
            endpoint=self.get_wingman_pro_azure_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/inworld/wingman-pro",
            endpoint=self.get_wingman_pro_inworld_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/voices/pocket-tts",
            endpoint=self.get_pocket_tts_voices,
            response_model=list[VoiceInfo],
            tags=tags,
        )

        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/pocket-tts",
            endpoint=self.play_pocket_tts,
            tags=tags,
        )
        
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/openai",
            endpoint=self.play_openai_tts,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/deepgram",
            endpoint=self.play_deepgram_tts,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/deepgram-openai/v1/voices",
            endpoint=self.get_deepgram_compatible_voices,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/deepgram-openai/v1/audio/speech",
            endpoint=self.synthesize_deepgram_compatible,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/openai-compatible",
            endpoint=self.play_openai_compatible_tts,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/elevenlabs",
            endpoint=self.play_elevenlabs_tts,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/hume",
            endpoint=self.play_hume,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/inworld",
            endpoint=self.play_inworld,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/edgetts",
            endpoint=self.play_edge_tts,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/xvasynth",
            endpoint=self.play_xvasynth_tts,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/wingman-pro/inworld",
            endpoint=self.play_wingman_pro_inworld,
            tags=tags,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/voices/preview/wingman-pro/azure",
            endpoint=self.play_wingman_pro_azure,
            tags=tags,
        )


    # GET /voices/elevenlabs
    async def get_elevenlabs_voices(self, api_key: str) -> list[VoiceInfo]:
        elevenlabs = ElevenLabs(api_key=api_key, wingman_name="")
        try:
            # Run the synchronous method in a separate thread
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as pool:
                voices = await loop.run_in_executor(
                    pool, elevenlabs.get_available_voices
                )

            convert = lambda voice: VoiceInfo(id=voice["voice_id"], name=voice["name"])
            result = [convert(voice) for voice in voices]
            return result
        except ValueError as e:
            self.printr.toast_error(f"Elevenlabs: \n{str(e)}")
            return []

    # GET /voices/hume
    async def get_hume_voices(self, api_key: str) -> list[VoiceInfo]:
        hume = Hume(api_key=api_key, wingman_name="")
        result = await hume.get_available_voices()
        return result

    # GET /voices/inworld
    async def get_inworld_voices(self, api_key: str) -> list[VoiceInfo]:
        inworld = Inworld(api_key=api_key, wingman_name="")
        result = await inworld.get_available_voices()
        return result

    # GET /voices/edge
    async def get_edge_voices(self) -> list[VoiceInfo]:
        # Microsoft's list changes rarely: once per Core start is enough.
        if not self.edge_voices:
            try:
                self.edge_voices = await get_edge_voices()
            except Exception as e:
                self.printr.toast_error(f"Edge TTS: \n{str(e)}")
        return self.edge_voices

    # GET /voices/deepgram
    async def get_deepgram_voices(self) -> list[VoiceInfo]:
        return DeepgramTts.get_available_voices()

    # GET /deepgram-openai/v1/voices
    async def get_deepgram_compatible_voices(self, request: Request) -> dict:
        self._require_loopback(request)
        return {
            "data": [
                {"id": voice.id, "name": voice.name}
                for voice in DeepgramTts.get_available_voices()
            ]
        }

    # POST /deepgram-openai/v1/audio/speech
    async def synthesize_deepgram_compatible(
        self, request: Request, payload: dict
    ) -> Response:
        """Translate an OpenAI-compatible TTS request into Deepgram Aura or Flux."""
        self._require_loopback(request)

        text = payload.get("input")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(status_code=400, detail="A non-empty input is required.")

        allowed_voices = {voice.id for voice in DeepgramTts.get_available_voices()}
        voice = payload.get("voice")
        model = payload.get("model")
        deepgram_model = (
            voice if isinstance(voice, str) and voice in allowed_voices
            else model if isinstance(model, str) and model in allowed_voices
            else None
        )
        if not deepgram_model:
            raise HTTPException(
                status_code=400,
                detail="Select a Deepgram Aura-2 or Flux voice in Wingman TTS settings.",
            )

        api_key = self.secret_keeper.secrets.get("deepgram", "")
        if not api_key:
            try:
                api_key = await self.secret_keeper.retrieve(
                    requester="Deepgram TTS", key="deepgram"
                )
            except ValueError:
                api_key = ""
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Enter the Deepgram API key in Wingman's key prompt, then retry.",
            )

        response_format = payload.get("response_format", "mp3")
        if response_format == "pcm":
            params: dict[str, str | int | float] = {
                "model": deepgram_model,
                "encoding": "linear16",
                "sample_rate": 24000,
                "container": "none",
            }
        elif response_format == "wav":
            params = {
                "model": deepgram_model,
                "encoding": "linear16",
                "sample_rate": 24000,
                "container": "wav",
            }
        elif response_format in ("mp3", None):
            params = {"model": deepgram_model, "encoding": "mp3"}
        else:
            raise HTTPException(
                status_code=400,
                detail="Deepgram Aura and Flux support mp3, wav, or pcm output here.",
            )

        speed = payload.get("speed")
        if isinstance(speed, (int, float)) and not isinstance(speed, bool):
            if not 0.5 <= speed <= 1.5:
                raise HTTPException(
                    status_code=400, detail="Deepgram speed must be between 0.5 and 1.5."
                )
            params["speed"] = speed

        deepgram_tts = DeepgramTts(api_key=api_key, config=None)
        if deepgram_model.startswith("flux-") and response_format == "pcm":
            audio_stream = deepgram_tts.stream_flux_audio(
                text=text,
                config=DeepgramTtsConfig(model=deepgram_model),
                params=params,
            )
            try:
                first_chunk = await anext(audio_stream)
            except StopAsyncIteration as exc:
                await audio_stream.aclose()
                raise HTTPException(
                    status_code=502,
                    detail="Deepgram Flux returned no audio for this text.",
                ) from exc
            except Exception as exc:
                await audio_stream.aclose()
                self.printr.print(
                    f"Deepgram Flux streaming TTS failed ({type(exc).__name__}).",
                    server_only=True,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Deepgram could not stream this Flux voice.",
                ) from exc

            async def audio_chunks():
                try:
                    yield first_chunk
                    async for chunk in audio_stream:
                        yield chunk
                except Exception as exc:
                    self.printr.print(
                        f"Deepgram Flux audio stream ended early ({type(exc).__name__}).",
                        server_only=True,
                    )
                    raise
                finally:
                    await audio_stream.aclose()

            return StreamingResponse(
                audio_chunks(),
                media_type="audio/pcm",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        try:
            audio = await deepgram_tts.request_audio(
                text=text,
                config=DeepgramTtsConfig(model=deepgram_model),
                params=params,
            )
        except httpx.HTTPStatusError as exc:
            self.printr.print(
                f"Deepgram compatible TTS returned HTTP {exc.response.status_code}.",
                server_only=True,
            )
            raise HTTPException(
                status_code=502, detail="Deepgram could not synthesize this text."
            ) from exc
        except httpx.RequestError as exc:
            self.printr.print(
                f"Deepgram compatible TTS request failed: {exc}", server_only=True
            )
            raise HTTPException(
                status_code=502, detail="Could not reach the Deepgram TTS API."
            ) from exc

        content_type = (
            "audio/pcm" if response_format == "pcm"
            else audio.headers.get("content-type", "audio/mpeg").split(";")[0]
        )
        return Response(content=audio.content, media_type=content_type)

    @staticmethod
    def _require_loopback(request: Request) -> None:
        host = request.client.host if request.client else ""
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
        if not is_loopback:
            raise HTTPException(status_code=403, detail="This endpoint is local-only.")

    # GET /voices/openai-compatible
    async def get_openai_compatible_voices(
        self,
        api_key: str,
        base_url: str,
        voices_endpoint: str | None = None,
    ) -> list[VoiceInfo]:
        openai_compatible = OpenAiCompatibleTts(api_key=api_key, base_url=base_url)
        return await openai_compatible.get_available_voices(
            voices_endpoint=voices_endpoint
        )

    # GET /voices/azure/wingman-pro
    def get_wingman_pro_azure_voices(
        self, filter_language: str = None
    ) -> list[VoiceInfo]:
        wingman_pro = WingmanSubscription(
            wingman_name="", settings=self.config_manager.settings_config.wingman_pro
        )
        return wingman_pro.get_available_azure_voices(filter_language=filter_language)

    # GET /voices/inworld/wingman-pro
    def get_wingman_pro_inworld_voices(
        self, filter_language: str = None
    ) -> list[VoiceInfo]:
        wingman_pro = WingmanSubscription(
            wingman_name="", settings=self.config_manager.settings_config.wingman_pro
        )
        voices = wingman_pro.get_available_inworld_voices(
            filter_language=filter_language
        )
        return voices

    def _spoken(self, text: str, provider: TtsProvider, as_written: bool) -> str:
        """A preview says the text the way a Wingman would: with the
        pronunciation rules. The pronunciation editor asks for a word as
        written, to compare it with the spelling that fixes it."""
        if as_written:
            return text
        settings = self.config_manager.settings_config
        return speech_text.prepare_for_speech(
            text,
            settings.spoken_language,
            settings.pronunciation.rules,
            settings.pronunciation.presets,
            reads_numbers=provider in speech_text.VOICES_THAT_READ_NUMBERS,
        )

    async def _run_playback(self, playback):
        """Run a playback coroutine in a worker thread with its own event loop.

        Playback previews block their loop (audio pumping + drain), so running
        them on the API event loop would freeze the server and make POST
        /stop-playback unreachable until the preview ends. This mirrors how
        wingmen play TTS via threaded_execution.

        Answers when the voice is done, stopped or replaced by the next
        preview: the client shows Stop until then. Providers without streaming
        (Edge, xVASynth) return as soon as their audio starts, so wait for it
        here.
        """
        await asyncio.to_thread(asyncio.run, playback)
        player = self.audio_player
        mine = player.playback_count
        while player.is_playing and player.playback_count == mine:
            await asyncio.sleep(0.1)

    # POST /play/openai
    async def play_openai_tts(
        self,
        text: str,
        api_key: str,
        voice: str,
        model: str,
        speed: float,
        sound_config: SoundConfig,
        stream: bool,
        as_written: bool = False,
    ):
        openai = OpenAi(api_key=api_key)
        await self._run_playback(
            openai.play_audio(
                text=self._spoken(text, TtsProvider.OPENAI, as_written),
                voice=voice,
                model=model,
                speed=speed,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
                stream=stream,
            )
        )

    # POST /voices/preview/deepgram
    async def play_deepgram_tts(
        self,
        text: str,
        api_key: str,
        config: DeepgramTtsConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        deepgram = DeepgramTts(api_key=api_key, config=None)
        await self._run_playback(
            deepgram.preview(
                text=self._spoken(text, TtsProvider.DEEPGRAM, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
            )
        )

    # POST /play/openai-compatible
    async def play_openai_compatible_tts(
        self,
        text: str,
        api_key: str,
        base_url: str,
        voice: str,
        model: str,
        speed: float,
        sound_config: SoundConfig,
        stream: bool,
        as_written: bool = False,
    ):
        openai = OpenAiCompatibleTts(api_key=api_key, base_url=base_url)
        await self._run_playback(
            openai.play_audio(
                text=self._spoken(text, TtsProvider.OPENAI_COMPATIBLE, as_written),
                voice=voice,
                model=model,
                speed=speed,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
                stream=stream,
            )
        )


    # POST /play/elevenlabs
    async def play_elevenlabs_tts(
        self,
        text: str,
        api_key: str,
        config: ElevenlabsConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        elevenlabs = ElevenLabs(api_key=api_key, wingman_name="")
        await self._run_playback(
            elevenlabs.play_audio(
                text=self._spoken(text, TtsProvider.ELEVENLABS, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
                stream=False,
                language=elevenlabs_language(
                    self.config_manager.settings_config.spoken_language,
                    self.config_manager.settings_config.other_language,
                ),
            )
        )

    # POST /play/edgetts
    async def play_edge_tts(
        self,
        text: str,
        config: EdgeTtsConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        edge = Edge()
        await self._run_playback(
            edge.play_audio(
                text=self._spoken(text, TtsProvider.EDGE_TTS, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
            )
        )

    # POST /play/hume
    async def play_hume(
        self,
        text: str,
        api_key: str,
        config: HumeConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        hume = Hume(api_key=api_key, wingman_name="")
        await self._run_playback(
            hume.play_audio(
                text=self._spoken(text, TtsProvider.HUME, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
            )
        )

    def _inworld_language(self) -> str:
        settings = self.config_manager.settings_config
        return inworld_language(settings.spoken_language, settings.other_language)

    # POST /play/inworld
    async def play_inworld(
        self,
        text: str,
        api_key: str,
        config: InworldConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        inworld = Inworld(api_key=api_key, wingman_name="")
        await self._run_playback(
            inworld.play_audio(
                text=self._spoken(text, TtsProvider.INWORLD, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
                language=self._inworld_language(),
            )
        )

    # POST /play/xvasynth
    async def play_xvasynth_tts(
        self,
        text: str,
        config: XVASynthTtsConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        await self._run_playback(
            self.xvasynth.play_audio(
                text=self._spoken(text, TtsProvider.XVASYNTH, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
            )
        )

    # GET /voices/pocket-tts
    async def get_pocket_tts_voices(self) -> list[VoiceInfo]:
        return await self.pocket_tts.get_available_voices()
    
    # POST /play/pocket-tts
    async def play_pocket_tts(
        self,
        text: str,
        config: PocketTTSConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        await self._run_playback(
            self.pocket_tts.play_audio(
                text=self._spoken(text, TtsProvider.POCKET_TTS, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
            )
        )


    # POST /play/wingman-pro/inworld
    async def play_wingman_pro_inworld(
        self,
        text: str,
        config: InworldConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        wingman_pro = WingmanSubscription(
            wingman_name="system",
            settings=self.config_manager.settings_config.wingman_pro,
        )
        await self._run_playback(
            wingman_pro.generate_inworld_speech(
                text=self._spoken(text, TtsProvider.WINGMAN_PRO, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
                language=self._inworld_language(),
                # A preview plays even a voice the plan does not include.
                preview=True,
            )
        )

    # POST /play/wingman-pro/azure
    async def play_wingman_pro_azure(
        self,
        text: str,
        config: AzureTtsConfig,
        sound_config: SoundConfig,
        as_written: bool = False,
    ):
        wingman_pro = WingmanSubscription(
            wingman_name="system",
            settings=self.config_manager.settings_config.wingman_pro,
        )
        await self._run_playback(
            wingman_pro.generate_azure_speech(
                text=self._spoken(text, TtsProvider.WINGMAN_PRO, as_written),
                config=config,
                sound_config=sound_config,
                audio_player=self.audio_player,
                wingman_name="system",
                language=self._inworld_language(),
                preview=True,
            )
        )
