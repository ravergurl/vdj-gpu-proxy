import logging
import threading
import torch
import torchaudio
import numpy as np
from demucs import pretrained
from demucs.apply import apply_model
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

STEM_NAMES = ["drums", "bass", "other", "vocals"]


class StemsInferenceEngine:
    def __init__(self, model_name="htdemucs", device="cuda", segment_length=7.8, overlap=0.25):
        self.model_name = model_name
        self.device = device if torch.cuda.is_available() and device == "cuda" else "cpu"
        self.segment_length = segment_length
        self.overlap = overlap

        logger.info(
            f"Initializing Demucs inference engine (model={model_name}, device={self.device})"
        )
        try:
            self.model = pretrained.get_model(model_name)
            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            logger.error(f"Failed to load model '{model_name}': {e}")
            raise RuntimeError(f"Failed to load Demucs model: {e}") from e

    @property
    def gpu_memory_mb(self) -> int:
        if self.device == "cuda":
            return torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
        return 0

    def separate(self, audio: np.ndarray, sample_rate=44100) -> Dict[str, np.ndarray]:
        """
        Separate audio into stems.
        audio: np.ndarray of shape (channels, samples)
        """
        if audio.ndim == 1:
            audio = np.stack([audio, audio])

        if audio.ndim != 2:
            raise ValueError(
                f"Input audio must have 2 dimensions (channels, samples), got {audio.ndim}"
            )

        if audio.shape[0] > 2:
            if audio.shape[1] <= 2:
                audio = audio.T
            else:
                raise ValueError(
                    f"Invalid audio shape {audio.shape}. Expected (channels, samples) with 1 or 2 channels."
                )

        if audio.shape[0] not in [1, 2]:
            raise ValueError(
                f"Invalid number of channels: {audio.shape[0]}. Only mono/stereo supported."
            )

        duration_sec = audio.shape[1] / sample_rate
        if duration_sec > 60:
            logger.warning(f"Long audio detected ({duration_sec:.1f}s). OOM risk is high.")

        audio_tensor = torch.from_numpy(audio).float().to(self.device)

        if audio_tensor.dim() == 2:
            audio_tensor = audio_tensor.unsqueeze(0)

        with torch.no_grad():
            sources = apply_model(
                self.model,
                audio_tensor,
                device=self.device,
                shifts=1,
                split=True,
                overlap=self.overlap,
                progress=False,
            )[0]

        stems = {}
        for i, name in enumerate(self.model.sources):
            stems[name] = sources[i].cpu().numpy()

        return stems

    def separate_tensor(
        self, input_tensor: bytes, input_shape: Tuple[int, ...], dtype: int
    ) -> Tuple[Dict[str, bytes], Tuple[int, ...]]:
        """
        Processes raw tensor data and returns stem byte arrays.
        """
        if dtype != 1:
            raise ValueError(f"Unsupported dtype: {dtype}. Only FLOAT32 (1) is supported.")

        audio = np.frombuffer(input_tensor, dtype=np.float32)
        try:
            audio = audio.reshape(input_shape)
        except ValueError as e:
            raise ValueError(
                f"Cannot reshape buffer of size {len(input_tensor)} to {input_shape}: {e}"
            )

        stems_np = self.separate(audio)

        output_stems = {}
        output_shape = None
        for name, data in stems_np.items():
            output_stems[name] = data.tobytes()
            if output_shape is None:
                output_shape = data.shape
            elif output_shape != data.shape:
                logger.error(
                    f"Stem shape mismatch: {name} has {data.shape}, expected {output_shape}"
                )
                raise RuntimeError(f"Model output shape inconsistent for stem {name}")

        return output_stems, output_shape


_engine: Optional[StemsInferenceEngine] = None
_engine_lock = threading.Lock()


def get_engine(**kwargs) -> StemsInferenceEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = StemsInferenceEngine(**kwargs)
        elif kwargs:
            logger.warning(
                "get_engine called with kwargs but engine already initialized. Ignoring new configuration."
            )
    return _engine
