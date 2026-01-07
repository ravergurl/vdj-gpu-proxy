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
    def __init__(
        self, model_name="htdemucs", device="cuda", segment_length=7.8, overlap=0.25
    ):
        self.model_name = model_name
        self.device = (
            device if torch.cuda.is_available() and device == "cuda" else "cpu"
        )
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
        # Ensure (channels, samples)
        if audio.ndim == 1:
            audio = np.stack([audio, audio])
        elif audio.shape[0] > 2 and audio.shape[1] <= 2:
            audio = audio.T

        audio_tensor = torch.from_numpy(audio).float().to(self.device)

        # Add batch dim
        if audio_tensor.dim() == 2:
            audio_tensor = audio_tensor.unsqueeze(0)

        with torch.no_grad():
            # apply_model returns (batch, stems, channels, samples)
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
            # Normalize to requested STEM_NAMES if needed, but demucs uses these exactly
            stems[name] = sources[i].cpu().numpy()

        return stems

    def separate_tensor(
        self, input_tensor: bytes, input_shape: Tuple[int, ...], dtype: int
    ) -> Tuple[Dict[str, bytes], Tuple[int, ...]]:
        """
        Processes raw tensor data and returns stem byte arrays.
        """
        # Assume float32 (dtype=1 in ONNX)
        audio = np.frombuffer(input_tensor, dtype=np.float32).reshape(input_shape)
        stems_np = self.separate(audio)

        output_stems = {}
        output_shape = None
        for name, data in stems_np.items():
            output_stems[name] = data.tobytes()
            if output_shape is None:
                output_shape = data.shape

        return output_stems, output_shape


_engine: Optional[StemsInferenceEngine] = None
_engine_lock = threading.Lock()


def get_engine(**kwargs) -> StemsInferenceEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = StemsInferenceEngine(**kwargs)
    return _engine
