"""Ingest pipeline: STT + scene detection in one pass."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.ingestor.scenes import SceneCut, detect_scenes, extract_thumbnail
from app.services.ingestor.stt import STTResult, transcribe


@dataclass
class IngestResult:
    stt: STTResult
    scenes: list[SceneCut]


def ingest(
    media_path: Path,
    scenes_dir: Path | None = None,
    extract_thumbs: bool = True,
    language: str = "ko",
) -> IngestResult:
    stt = transcribe(media_path, language=language)
    scenes = detect_scenes(media_path)

    if extract_thumbs and scenes_dir is not None:
        out_dir = scenes_dir / media_path.stem
        for sc in scenes:
            mid = (sc.start_ms + sc.end_ms) // 2
            thumb = out_dir / f"scene-{sc.idx:03d}.jpg"
            try:
                extract_thumbnail(media_path, mid, thumb)
                sc.thumb_path = thumb
            except Exception:  # noqa: BLE001 — thumbs are optional
                sc.thumb_path = None

    return IngestResult(stt=stt, scenes=scenes)
