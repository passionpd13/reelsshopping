"""ffmpeg-based composer.

Takes per-segment TTS audio + b-roll picks + ASS subtitles and produces
a vertical 1080x1920 mp4. Designed to be deterministic and idempotent:
same inputs + same spec → same output.

Pipeline overview
-----------------
1. For each segment i:
   - Pick a b-roll clip (or synthesize a color/still if none).
   - Cut [broll_in_ms, broll_in_ms + tts_duration_ms] from the source.
   - Scale+crop to 9:16 (1080x1920), apply subtle time-stretch if needed.
2. Concatenate segment videos via concat demuxer → silent_reel.mp4
3. Concatenate segment TTS wavs → narration.wav
4. Mix narration + optional BGM (BGM ducked under narration) → final_audio.wav
5. Burn ASS subtitles onto silent_reel.
6. Mux final_audio onto subtitled video → output.mp4
"""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import get_logger
from app.services.subtitle.ass_builder import SegmentCaption, SubtitleStyle, build_ass

log = get_logger(__name__)


@dataclass
class BrollClip:
    source_path: Path
    in_ms: int
    out_ms: int


@dataclass
class SegmentInput:
    tts_audio_path: Path
    tts_duration_ms: int
    text: str
    emphasis_words: list[str] = field(default_factory=list)
    broll: BrollClip | None = None


@dataclass
class ComposeSpec:
    segments: list[SegmentInput]
    output_path: Path
    work_dir: Path
    width: int = 1080
    height: int = 1920
    fps: int = 30
    bgm_path: Path | None = None
    bgm_volume: float = 0.12  # relative gain
    subtitle_style: SubtitleStyle | None = None


@dataclass
class RenderResult:
    output_path: Path
    duration_ms: int
    width: int
    height: int


def _run(cmd: list[str]) -> None:
    log.debug("ffmpeg: %s", " ".join(shlex.quote(c) for c in cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {res.stderr[-2000:]}")


def _cut_and_fit_broll(
    clip: BrollClip | None,
    duration_ms: int,
    width: int,
    height: int,
    fps: int,
    out_path: Path,
) -> Path:
    """Cut a broll segment to `duration_ms` and fit 9:16.

    If no b-roll is provided, synthesize a dark-gray still with fps matching.
    """
    dur_sec = max(0.1, duration_ms / 1000.0)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if clip is None:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1a1a1a:s={width}x{height}:r={fps}",
            "-t", f"{dur_sec:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            str(out_path),
        ]
        _run(cmd)
        return out_path

    in_sec = max(0.0, clip.in_ms / 1000.0)
    src_dur = max(0.1, (clip.out_ms - clip.in_ms) / 1000.0)
    # time-stretch to match segment duration if within 0.7x~1.4x
    rate = src_dur / dur_sec
    rate = max(0.7, min(1.4, rate))
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"setpts=PTS/{rate:.4f},fps={fps}"
    )
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{in_sec:.3f}", "-t", f"{src_dur:.3f}", "-i", str(clip.source_path),
        "-an", "-vf", vf, "-t", f"{dur_sec:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def _concat_videos(clips: list[Path], out_path: Path, work_dir: Path) -> Path:
    list_file = work_dir / "concat_v.txt"
    list_file.write_text("\n".join(f"file '{p.absolute()}'" for p in clips))
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(out_path),
    ]
    _run(cmd)
    return out_path


def _concat_audios(audios: list[Path], out_path: Path, work_dir: Path) -> Path:
    """Concat wavs losslessly (re-encode to pcm_s16le 48k mono for consistency)."""
    list_file = work_dir / "concat_a.txt"
    list_file.write_text("\n".join(f"file '{p.absolute()}'" for p in audios))
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def _mix_with_bgm(
    narration: Path,
    bgm: Path | None,
    bgm_volume: float,
    total_duration_ms: int,
    out_path: Path,
) -> Path:
    if bgm is None:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(narration),
            "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k",
            str(out_path),
        ]
        _run(cmd)
        return out_path

    dur_sec = total_duration_ms / 1000.0
    # sidechain ducking: BGM dips when narration is loud
    filter_complex = (
        f"[1:a]aloop=loop=-1:size=2e9,atrim=duration={dur_sec:.3f},"
        f"volume={bgm_volume}[bgm];"
        f"[0:a][bgm]sidechaincompress=threshold=0.05:ratio=8:attack=5:release=200[mix]"
    )
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(narration), "-i", str(bgm),
        "-filter_complex", filter_complex,
        "-map", "[mix]", "-ar", "48000", "-ac", "2",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def _burn_subtitles(video: Path, ass_file: Path, out_path: Path) -> Path:
    # escape colons and special chars for ffmpeg filter path syntax
    ass_str = str(ass_file).replace(":", r"\:").replace("'", r"\'")
    vf = f"subtitles='{ass_str}'"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-an", str(out_path),
    ]
    _run(cmd)
    return out_path


def _mux(video: Path, audio: Path, out_path: Path) -> Path:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        "-movflags", "+faststart",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def render_reel(spec: ComposeSpec) -> RenderResult:
    spec.work_dir.mkdir(parents=True, exist_ok=True)
    spec.output_path.parent.mkdir(parents=True, exist_ok=True)

    seg_videos: list[Path] = []
    captions: list[SegmentCaption] = []
    cursor = 0
    for i, seg in enumerate(spec.segments):
        seg_video = spec.work_dir / f"seg_{i:03d}.mp4"
        _cut_and_fit_broll(
            seg.broll, seg.tts_duration_ms, spec.width, spec.height, spec.fps, seg_video
        )
        seg_videos.append(seg_video)
        captions.append(
            SegmentCaption(
                start_ms=cursor,
                end_ms=cursor + seg.tts_duration_ms,
                text=seg.text,
                emphasis_words=seg.emphasis_words,
            )
        )
        cursor += seg.tts_duration_ms

    total_ms = cursor
    log.info("Rendering reel: %d segments, %.2fs total", len(spec.segments), total_ms / 1000.0)

    silent_reel = _concat_videos(seg_videos, spec.work_dir / "silent_reel.mp4", spec.work_dir)

    narration = _concat_audios(
        [s.tts_audio_path for s in spec.segments],
        spec.work_dir / "narration.wav",
        spec.work_dir,
    )
    final_audio = _mix_with_bgm(
        narration, spec.bgm_path, spec.bgm_volume, total_ms, spec.work_dir / "final_audio.m4a"
    )

    style = spec.subtitle_style or SubtitleStyle(video_width=spec.width, video_height=spec.height)
    ass_path = spec.work_dir / "subs.ass"
    ass_path.write_text(build_ass(captions, style), encoding="utf-8")

    subtitled = _burn_subtitles(silent_reel, ass_path, spec.work_dir / "subtitled.mp4")
    output = _mux(subtitled, final_audio, spec.output_path)

    return RenderResult(
        output_path=output,
        duration_ms=total_ms,
        width=spec.width,
        height=spec.height,
    )
