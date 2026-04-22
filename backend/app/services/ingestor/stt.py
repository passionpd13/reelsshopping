"""faster-whisper based speech-to-text.

Returns timestamped segments. Model is lazily loaded once per process.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class STTSegment:
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None


@dataclass
class STTResult:
    lang: str
    full_text: str
    segments: list[STTSegment]


@lru_cache(maxsize=1)
def _get_model():
    from faster_whisper import WhisperModel

    s = get_settings()
    log.info(
        "Loading whisper model=%s device=%s compute_type=%s",
        s.whisper_model, s.whisper_device, s.whisper_compute_type,
    )
    return WhisperModel(s.whisper_model, device=s.whisper_device, compute_type=s.whisper_compute_type)


def transcribe(media_path: Path, language: str = "ko") -> STTResult:
    model = _get_model()
    segments_it, info = model.transcribe(
        str(media_path),
        language=language,
        vad_filter=True,
        word_timestamps=False,
        beam_size=5,
    )

    segs: list[STTSegment] = []
    parts: list[str] = []
    for s in segments_it:
        text = (s.text or "").strip()
        if not text:
            continue
        segs.append(
            STTSegment(
                start_ms=int(s.start * 1000),
                end_ms=int(s.end * 1000),
                text=text,
                confidence=getattr(s, "avg_logprob", None),
            )
        )
        parts.append(text)

    return STTResult(lang=info.language or language, full_text=" ".join(parts), segments=segs)
