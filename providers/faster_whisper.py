"""Local Faster-Whisper provider used by push-to-talk and voice activation."""

import threading
from typing import Optional

from api.enums import LogType
from services.printr import Printr


MODEL_SIZE = "large-v3-turbo"
LANGUAGE = "en"
BEAM_SIZE = 5


class FasterWhisper:
    """PTT's Windows profile: large-v3-turbo, English, CUDA/float16."""

    def __init__(self):
        self.printr = Printr()
        self.model = None
        self.device = "cuda"
        self.compute_type = "float16"
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if self.model is not None:
                return
            from faster_whisper import WhisperModel

            try:
                import ctranslate2
                if ctranslate2.get_cuda_device_count() < 1:
                    raise RuntimeError("No CUDA device is available")
            except Exception as exc:
                self.device = "cpu"
                self.compute_type = "int8"
                self.printr.print(
                    f"Faster-Whisper is using CPU ({exc}).",
                    server_only=True,
                    color=LogType.WARNING,
                )
            self.printr.print(
                f"Loading Faster-Whisper {MODEL_SIZE} on {self.device} ({self.compute_type}); "
                "the first load downloads the model.",
                server_only=True,
                color=LogType.INFO,
            )
            try:
                self.model = WhisperModel(
                    MODEL_SIZE, device=self.device, compute_type=self.compute_type
                )
            except Exception:
                if self.device != "cuda":
                    raise
                # PTT's Windows CUDA runtime differs from Core's bundled ONNX
                # runtime. Keep the provider usable if CTranslate2 cannot load
                # the GPU backend with the machine's available CUDA libraries.
                self.device, self.compute_type = "cpu", "int8"
                self.printr.print(
                    "Faster-Whisper CUDA initialization failed; falling back to CPU/int8.",
                    server_only=True,
                    color=LogType.WARNING,
                )
                self.model = WhisperModel(
                    MODEL_SIZE, device=self.device, compute_type=self.compute_type
                )

    def transcribe(self, filename: str, initial_prompt: Optional[str] = None) -> str | None:
        if self.model is None:
            raise RuntimeError("Faster-Whisper model is not loaded")
        segments, _info = self.model.transcribe(
            filename,
            language=LANGUAGE,
            beam_size=BEAM_SIZE,
            initial_prompt=initial_prompt or None,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text or None

    def unload(self):
        with self._lock:
            if self.model is None:
                return
            del self.model
            self.model = None
