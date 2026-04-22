"""ASS subtitle builder for burn-in via ffmpeg `subtitles` filter.

Each TTS-generated segment becomes one caption block. Multi-line wrapping
respects a max-characters-per-line budget so Korean captions stay centered
at the bottom-third of a 9:16 frame without overflow.

Timing is taken from per-segment durations (known exactly from wav length);
word-level emphasis uses the estimated word timings from `tts.supertone`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubtitleStyle:
    font_name: str = "Noto Sans CJK KR"
    font_size: int = 64
    primary_color: str = "FFFFFF"
    outline_color: str = "000000"
    back_color: str = "000000"
    outline: int = 4
    shadow: int = 0
    bold: bool = True
    margin_v: int = 280  # px from bottom
    max_chars_per_line: int = 14
    alignment: int = 2  # bottom-center (ASS numpad)
    video_width: int = 1080
    video_height: int = 1920


@dataclass
class SegmentCaption:
    start_ms: int
    end_ms: int
    text: str
    emphasis_words: list[str] = field(default_factory=list)


def segments_to_captions(
    segments: list[tuple[int, int, str, list[str]]],
) -> list[SegmentCaption]:
    """Convenience: (start_ms, end_ms, text, emphasis_words) tuples → captions."""
    return [SegmentCaption(s, e, t, em) for s, e, t, em in segments]


def _ts(ms: int) -> str:
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms_ = divmod(rem, 1000)
    cs = ms_ // 10  # centiseconds for ASS
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_color(hex_rgb: str, alpha: int = 0) -> str:
    """ASS color is &HAABBGGRR."""
    h = hex_rgb.lstrip("#").upper()
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = f"{alpha:02X}"
    return f"&H{a}{b}{g}{r}"


def _wrap(text: str, max_chars: int) -> list[str]:
    """Break a Korean-friendly caption into N lines without splitting words."""
    text = text.strip()
    if not text:
        return []
    tokens = text.split()
    if not tokens:
        # fallback: hard chunk by chars
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    lines: list[str] = []
    cur = ""
    for tok in tokens:
        candidate = f"{cur} {tok}".strip()
        if len(candidate) <= max_chars or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = tok
    if cur:
        lines.append(cur)
    return lines


def _emphasize(line: str, emphasis: list[str]) -> str:
    if not emphasis:
        return line
    out = line
    for word in emphasis:
        if not word:
            continue
        out = out.replace(word, "{\\c&H00F2FF&\\b1}" + word + "{\\c&HFFFFFF&\\b0}")
    return out


def build_ass(
    captions: list[SegmentCaption],
    style: SubtitleStyle,
) -> str:
    header = _build_header(style)
    events = []
    for cap in captions:
        if cap.end_ms <= cap.start_ms or not cap.text.strip():
            continue
        lines = _wrap(cap.text, style.max_chars_per_line)
        text_block = r"\N".join(_emphasize(ln, cap.emphasis_words) for ln in lines)
        events.append(
            f"Dialogue: 0,{_ts(cap.start_ms)},{_ts(cap.end_ms)},Default,,0,0,0,,{text_block}"
        )
    return header + "\n".join(events) + "\n"


def _build_header(s: SubtitleStyle) -> str:
    primary = _ass_color(s.primary_color)
    outline = _ass_color(s.outline_color)
    back = _ass_color(s.back_color)
    bold = -1 if s.bold else 0
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        f"PlayResX: {s.video_width}\n"
        f"PlayResY: {s.video_height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{s.font_name},{s.font_size},{primary},{primary},{outline},{back},"
        f"{bold},0,0,0,100,100,0,0,1,{s.outline},{s.shadow},{s.alignment},60,60,{s.margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
