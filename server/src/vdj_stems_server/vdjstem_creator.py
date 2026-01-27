"""
VDJStem file creator - creates MP4 files with multiple audio streams for VirtualDJ.

VDJStem format:
- MP4 container with 4 stereo audio streams (AAC encoded)
- Stream order: vocals, instruments (other), bass, drums
- Each stream is stereo 44.1kHz
"""

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# Stem order expected by VDJ (based on research)
VDJSTEM_ORDER = ["vocals", "other", "bass", "drums"]

# Map from Demucs stem names to VDJ stem names
DEMUCS_TO_VDJ = {
    "vocals": "vocals",
    "other": "other",  # instruments/melody
    "bass": "bass",
    "drums": "drums",
}


def compute_audio_hash(audio: np.ndarray, sample_rate: int = 44100) -> str:
    """
    Compute a hash of the audio data for identification.
    Uses first 10 seconds of audio for fast hashing.
    """
    # Use first 10 seconds
    max_samples = sample_rate * 10
    if audio.shape[-1] > max_samples:
        audio_sample = audio[..., :max_samples]
    else:
        audio_sample = audio

    # Quantize to 16-bit to reduce hash sensitivity to tiny differences
    audio_16bit = (audio_sample * 32767).astype(np.int16)

    # Compute SHA256 hash
    hash_obj = hashlib.sha256(audio_16bit.tobytes())
    return hash_obj.hexdigest()[:16]  # Use first 16 chars


def create_vdjstem_file(
    stems: Dict[str, np.ndarray],
    output_path: str,
    sample_rate: int = 44100,
    audio_bitrate: str = "192k"
) -> bool:
    """
    Create a VDJStem MP4 file from separated stems.

    Args:
        stems: Dict mapping stem names to numpy arrays (shape: [channels, samples])
        output_path: Path for the output .vdjstem file
        sample_rate: Audio sample rate (default 44100)
        audio_bitrate: AAC encoding bitrate (default 192k)

    Returns:
        True if successful, False otherwise
    """
    temp_dir = None
    try:
        # Create temp directory for intermediate files
        temp_dir = tempfile.mkdtemp(prefix="vdjstem_")
        temp_files = []

        # Write each stem as a temporary WAV file
        for stem_name in VDJSTEM_ORDER:
            if stem_name not in stems:
                logger.error(f"Missing stem: {stem_name}")
                return False

            stem_data = stems[stem_name]

            # Ensure stereo (2, samples) format
            if stem_data.ndim == 1:
                stem_data = np.stack([stem_data, stem_data])
            elif stem_data.shape[0] > stem_data.shape[1]:
                # Likely (samples, channels) - transpose
                stem_data = stem_data.T

            # Ensure 2 channels
            if stem_data.shape[0] == 1:
                stem_data = np.stack([stem_data[0], stem_data[0]])
            elif stem_data.shape[0] > 2:
                stem_data = stem_data[:2]

            # Write to temp WAV
            temp_wav = os.path.join(temp_dir, f"{stem_name}.wav")
            # soundfile expects (samples, channels)
            sf.write(temp_wav, stem_data.T, sample_rate)
            temp_files.append(temp_wav)
            logger.debug(f"Wrote temp stem: {temp_wav}, shape: {stem_data.shape}")

        # Use ffmpeg to create MP4 with multiple audio streams
        # Each stream is encoded as AAC
        output_temp = os.path.join(temp_dir, "output.mp4")

        ffmpeg_cmd = ["ffmpeg", "-y"]

        # Add inputs
        for temp_wav in temp_files:
            ffmpeg_cmd.extend(["-i", temp_wav])

        # Map all audio streams
        for i in range(len(temp_files)):
            ffmpeg_cmd.extend(["-map", f"{i}:a"])

        # Encode settings for all streams
        ffmpeg_cmd.extend([
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-ar", str(sample_rate),
            "-ac", "2",
            output_temp
        ])

        logger.info(f"Running ffmpeg: {' '.join(ffmpeg_cmd)}")

        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error(f"ffmpeg failed: {result.stderr}")
            return False

        # Move to final location
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.move(output_temp, output_path)

        logger.info(f"Created VDJStem file: {output_path}")
        return True

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timed out")
        return False
    except Exception as e:
        logger.exception(f"Failed to create VDJStem file: {e}")
        return False
    finally:
        # Cleanup temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def get_vdjstem_path(
    audio_hash: str,
    stems_folder: Optional[str] = None
) -> str:
    """
    Get the path where a VDJStem file should be stored.

    Args:
        audio_hash: Hash of the source audio
        stems_folder: Base folder for stems (default: system temp)

    Returns:
        Full path to the .vdjstem file
    """
    if stems_folder is None:
        stems_folder = os.path.join(tempfile.gettempdir(), "VDJ-Stems")

    # Create a subdirectory based on first 2 chars of hash
    subdir = audio_hash[:2]
    stem_dir = os.path.join(stems_folder, subdir)

    return os.path.join(stem_dir, f"{audio_hash}.vdjstem")


def check_vdjstem_exists(audio_hash: str, stems_folder: Optional[str] = None) -> Optional[str]:
    """
    Check if a VDJStem file already exists for the given audio hash.

    Returns:
        Path to existing file, or None if not found
    """
    path = get_vdjstem_path(audio_hash, stems_folder)
    if os.path.exists(path):
        return path
    return None
