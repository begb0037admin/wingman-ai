"""One place that turns a recording into text.

Push-to-talk and voice activation both land here, so what the user said is
transcribed by the provider chosen in Settings, whichever way the recording
was started. Before 3.2.2 push-to-talk read a per-wingman provider and voice
activation a global one; the same audio could take two different engines.

The provider objects are the shared singletons WingmanCore owns. Calls are
synchronous: every provider blocks on a model or an HTTP request, and both
callers already run on a worker thread.
"""

import traceback
import json
import re
from typing import TYPE_CHECKING, Callable, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

from api.enums import LogType, SttProvider
from services.audio.vocabulary import Vocabulary, apply_override, load_preset
from services.decision_gate import DecisionGate
from services.printr import Printr
from services.audio.common_words import common_words
from services.spoken_language import transcription_tag

if TYPE_CHECKING:
    from providers.parakeet import Parakeet
    from providers.faster_whisper import FasterWhisper
    from services.secret_keeper import SecretKeeper
    from services.settings_service import SettingsService


class SttService:
    def __init__(
        self,
        settings_service: "SettingsService",
        secret_keeper: "SecretKeeper",
        parakeet: "Parakeet",
        faster_whisper: Optional["FasterWhisper"] = None,
        get_hotwords: Optional[Callable[[], list[str]]] = None,
        app_root_path: str = ".",
    ):
        self.settings_service = settings_service
        self.app_root_path = app_root_path
        self.secret_keeper = secret_keeper
        self.parakeet = parakeet
        if faster_whisper is None:
            from providers.faster_whisper import FasterWhisper
            faster_whisper = FasterWhisper()
        self.faster_whisper = faster_whisper
        # Names the decoder should recognise, read fresh on every call so a
        # config switch (other wingmen, other names) is picked up without a
        # restart. WingmanCore hands in the names of the active wingmen.
        self.get_hotwords = get_hotwords or (lambda: [])
        self.printr = Printr()
        self._preset_cache: dict[str, list[str]] = {}
        # Reads settings_service on every call, so a toggle in the client
        # applies to the next utterance. See services/decision_gate.py.
        self.decision_gate = DecisionGate(wingman_name="STT", settings=settings_service.settings)

    @property
    def provider(self) -> SttProvider:
        return self.settings_service.settings.stt.provider

    def transcribe(self, filename: str) -> str | None:
        """Text for the recording, or None when there was nothing to hear or
        the provider failed. Failures are reported to the user here; callers
        only need to handle the None."""
        provider = self.provider
        try:
            text = self._transcribe(provider, filename)
        except Exception as e:
            self.printr.print(
                f"Error during transcription using '{provider.value}': {str(e)}",
                color=LogType.ERROR,
            )
            self.printr.print(
                traceback.format_exc(), color=LogType.ERROR, server_only=True
            )
            return None

        text = (text or "").strip()
        if not text:
            self.printr.print(
                "ignored empty transcription - probably just noise.",
                server_only=True,
            )
            return None
        corrected = self._correct(text)
        if corrected != text:
            self.printr.print(
                f"Vocabulary: '{text}' -> '{corrected}'", server_only=True, color=LogType.INFO
            )
        if provider == SttProvider.FASTER_WHISPER:
            return self._cleanup_transcript(text, corrected)
        return corrected

    @staticmethod
    def _cleanup_is_plausible(raw: str, cleaned: str) -> bool:
        """Reject Ollama answers or expansions; cleanup may only edit speech."""
        raw, cleaned = raw.strip(), cleaned.strip()
        if not cleaned:
            return False
        if len(cleaned) > max(len(raw) * 1.5, len(raw) + 30):
            return False
        if "\n" not in raw and sum(
            bool(re.match(r"^(?:[-*•]|\d+[.)])\s+", line.strip()))
            for line in cleaned.splitlines()
        ) >= 2:
            return False
        words = lambda value: set(re.findall(r"[a-z0-9']+", value.lower()))
        fillers = {"um", "uh", "like"}
        original = words(raw) - fillers
        result = words(cleaned) - fillers
        if original and len(original & result) / len(original) < 0.6:
            return False
        if result and len(result - original) / len(result) > 0.35:
            return False
        openers = (
            "i can", "i can't", "i cannot", "i don't", "i do not", "i'm", "i am",
            "here's", "here is", "let me", "of course", "absolutely", "sure",
            "certainly", "the answer", "as an ai", "happy to",
        )
        lower_raw, lower_cleaned = raw.lower().lstrip(), cleaned.lower().lstrip()
        if not any(lower_raw.startswith(opener) for opener in openers) and any(
            lower_cleaned.startswith(opener) for opener in openers
        ):
            return False
        return True

    def _cleanup_transcript(self, raw: str, corrected: str) -> str:
        """Use only the local Ollama endpoint; failures retain corrected speech."""
        payload = json.dumps({
            "model": "llama3.2:3b",
            "system": (
                "You edit speech transcripts; you are not a conversational assistant. "
                "Remove filler words and false starts, and fix punctuation and grammar. "
                "Preserve meaning and wording. Never answer questions or add content. "
                "Return only the edited transcript."
            ),
            "prompt": f"<transcript>\n{corrected}\n</transcript>",
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_predict": 512},
        }).encode("utf-8")
        request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                candidate = str(json.loads(response.read()).get("response", "")).strip()
            if self._cleanup_is_plausible(corrected, candidate):
                return candidate
            self.printr.print(
                "Ignored implausible local STT cleanup; keeping raw transcript.",
                server_only=True,
                color=LogType.WARNING,
            )
        except (URLError, TimeoutError, OSError, ValueError, TypeError) as exc:
            self.printr.print(
                f"Local STT cleanup unavailable; keeping raw transcript: {exc}",
                server_only=True,
                color=LogType.WARNING,
            )
        return corrected

    def _correct(self, text: str) -> str:
        """The transcript with the misheard names put right.

        Without the gate this is the fuzzy matcher on its own, which decides
        by letters and never touches a real word of the user's language. Its
        one silent mistake: a name the speech model heard as a real word
        stays that word, "station" never becomes "Stanton". Whether a word is
        the name or the everyday word is in the sentence around it, which is
        what the gate asks about.

        Every way this can fail — gate off, no key, provider down, model unsure
        — ends in the matcher's own answer, which is today's behaviour.
        """
        # Settings are re-read here rather than kept: SttService outlives every
        # save, and the gate must follow the switch the user just flipped.
        self.decision_gate.update_settings(self.settings_service.settings)
        vocabulary = self.vocabulary()
        if not self.decision_gate.active:
            return vocabulary.correct(text)

        proposals = vocabulary.proposals(text)
        if not proposals:
            return text
        confirmed = self.decision_gate.confirm_vocabulary(text, proposals)
        if confirmed is None:
            return vocabulary.correct(text)

        corrected = text
        for index in sorted(confirmed):
            heard, entry, _blocked = proposals[index]
            corrected = corrected.replace(heard, entry, 1)
        return corrected

    def vocabulary(self) -> Vocabulary:
        """The user's list plus the names of the active wingmen and whatever
        their skills added. Built per call; the lists are short and may
        change between two utterances."""
        stt = self.settings_service.settings.stt
        words = list(stt.vocabulary or []) + self.get_hotwords()
        for preset_id in stt.presets or []:
            if preset_id not in self._preset_cache:
                self._preset_cache[preset_id] = load_preset(self.app_root_path, preset_id)
            words += apply_override(
                self._preset_cache[preset_id], (stt.preset_overrides or {}).get(preset_id)
            )
        return Vocabulary(
            words,
            common_words=common_words(self.app_root_path, self.settings_service.settings.spoken_language),
        )

    def _parakeet_api_key(self) -> str:
        """The secret `parakeet`, for a remote server that wants a key.
        Optional like `local_llm`: never prompts, empty means keyless.
        "not-set" is the placeholder older migrations wrote."""
        key = str(self.secret_keeper.secrets.get("parakeet") or "").strip()
        return "" if key == "not-set" else key

    def _transcribe(self, provider: SttProvider, filename: str) -> str | None:
        stt = self.settings_service.settings.stt

        if provider == SttProvider.PARAKEET:
            result = self.parakeet.transcribe(
                config=stt.parakeet_config,
                filename=filename,
                api_key=self._parakeet_api_key(),
            )
            return result.text if result else None

        if provider == SttProvider.FASTER_WHISPER:
            # Decoder hints use the same live vocabulary as deterministic correction.
            hints = ", ".join(self.vocabulary().entries)
            return self.faster_whisper.transcribe(filename, initial_prompt=hints)

        if provider == SttProvider.WINGMAN_PRO:
            from providers.wingman_subscription import WingmanSubscription

            subscription = WingmanSubscription(
                wingman_name="system",
                settings=self.settings_service.settings.wingman_pro,
            )
            result = subscription.transcribe(
                filename=filename,
                languages=[
                    tag
                    for tag in [transcription_tag(self.settings_service.settings.spoken_language)]
                    if tag
                ],
            )
            return result.text if result else None

        self.printr.toast_error(f"Unknown speech-to-text provider '{provider}'.")
        return None
