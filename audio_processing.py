"""Utilities for validating uploaded audio files and transcribing them into text."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Union

AudioPath = Union[str, Path]
SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".webm",
}


@lru_cache(maxsize=4)
def _load_whisper_model(model_size: str, device: str, compute_type: str):
    """Load and cache the configured Whisper model for the current process."""
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device=device, compute_type=compute_type)


def validate_audio_file(file_path: AudioPath) -> Path:
    """Validate an uploaded audio file and return a pathlib.Path to it."""
    path = Path(file_path)

    if not path.exists():
        raise ValueError("The uploaded file was not found on disk.")
    if not path.is_file():
        raise ValueError("The uploaded path is not a valid file.")
    if path.stat().st_size == 0:
        raise ValueError("The uploaded audio file is empty. Please upload a non-empty recording.")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(
            "Unsupported audio format. Please upload a .wav, .mp3, .m4a, .aac, .flac, .ogg, or .webm file."
        )

    return path


def _normalize_to_wav(file_path: AudioPath) -> Path:
    """Convert audio to compact mono 16 kHz PCM for faster ASR processing."""
    source_path = validate_audio_file(file_path)
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise ValueError(
            "FFmpeg is required to process audio files. Install FFmpeg and add it to PATH."
        )

    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav.close()
    normalized_path = Path(temp_wav.name)

    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-threads",
                "0",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-acodec",
                "pcm_s16le",
                str(normalized_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - runtime dependency issue handling
        if normalized_path.exists():
            normalized_path.unlink(missing_ok=True)
        raise ValueError(
            "Audio conversion timed out. The file may be too large or damaged."
        ) from exc
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover - runtime dependency issue handling
        if normalized_path.exists():
            normalized_path.unlink(missing_ok=True)
        raise ValueError(
            "Unable to read the uploaded audio file. Please upload a valid recording that is not corrupted or unreadable."
        ) from exc

    return normalized_path


def transcribe_audio(file_path: AudioPath, model_size: str | None = None) -> str:
    """Transcribe an uploaded meeting audio file into a raw English transcript."""
    normalized_path = _normalize_to_wav(file_path)

    try:
        selected_model = model_size or os.getenv("WHISPER_MODEL", "base.en")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        model = _load_whisper_model(selected_model, device, compute_type)
        segments, _info = model.transcribe(
            str(normalized_path),
            language="en",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        transcript = "\n".join(
            segment.text.strip() for segment in segments if segment.text and segment.text.strip()
        )

        if not transcript.strip():
            raise ValueError("No recognizable speech was detected in the uploaded audio file.")

        return transcript.strip()
    except Exception as exc:  # pragma: no cover - runtime ASR dependency issue handling
        raise RuntimeError(f"Speech-to-text processing failed: {exc}") from exc
    finally:
        if normalized_path.exists():
            normalized_path.unlink(missing_ok=True)
