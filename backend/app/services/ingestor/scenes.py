"""Scene cut detection using PySceneDetect's content detector."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class SceneCut:
    idx: int
    start_ms: int
    end_ms: int
    thumb_path: Path | None = None


def detect_scenes(media_path: Path, threshold: float = 27.0) -> list[SceneCut]:
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(str(media_path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video, show_progress=False)
    scenes = manager.get_scene_list()
    if not scenes:
        # whole file as one scene
        duration = video.duration.get_seconds() if video.duration else 0
        return [SceneCut(idx=0, start_ms=0, end_ms=int(duration * 1000))]

    return [
        SceneCut(idx=i, start_ms=int(s[0].get_seconds() * 1000), end_ms=int(s[1].get_seconds() * 1000))
        for i, s in enumerate(scenes)
    ]


def extract_thumbnail(media_path: Path, at_ms: int, out_path: Path) -> Path:
    """Grab a single frame as jpg via ffmpeg. Fast, no re-encode of video."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t = max(0.0, at_ms / 1000.0)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{t:.3f}", "-i", str(media_path),
        "-frames:v", "1", "-q:v", "4", str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path
