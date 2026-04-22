"""Supertone TTS client.

API reference: https://docs.supertoneapi.com/
- GET  /v1/voices                              → list voices
- POST /v1/text-to-speech/{voice_id}           → synthesize (binary wav by default)
- POST /v1/text-to-speech/{voice_id}/stream    → streaming (NDJSON if include_phonemes)

Authenticated via `x-sup-api-key` header.
"""
from __future__ import annotations

import json
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class Voice:
    id: str
    name: str
    language: str | None = None
    gender: str | None = None
    style: str | None = None
    age: str | None = None
    use_case: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class WordTiming:
    word: str
    start_ms: int
    end_ms: int


@dataclass
class TTSResult:
    audio_path: Path
    duration_ms: int
    word_timings: list[WordTiming]
    char_count: int


class SupertoneClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        s = get_settings()
        self.api_key = api_key or s.supertone_api_key
        self.base_url = (base_url or s.supertone_base_url).rstrip("/")
        if not self.api_key:
            raise RuntimeError("SUPERTONE_API_KEY is not set")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"x-sup-api-key": self.api_key, "Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SupertoneClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Voices
    # ------------------------------------------------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def list_voices(self) -> list[Voice]:
        r = self._client.get("/v1/voices")
        r.raise_for_status()
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        return [_to_voice(v) for v in (items or [])]

    def search_voices(self, language: str | None = None, style: str | None = None) -> list[Voice]:
        params: dict[str, str] = {}
        if language:
            params["language"] = language
        if style:
            params["style"] = style
        r = self._client.get("/v1/voices/search", params=params)
        r.raise_for_status()
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        return [_to_voice(v) for v in (items or [])]

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def synthesize(
        self,
        text: str,
        voice_id: str,
        out_path: Path,
        *,
        language: str = "ko",
        style: str = "neutral",
        model: str = "sona_speech_1",
        output_format: str = "wav",
        pitch_shift: float = 0.0,
        pitch_variance: float = 1.0,
        speed: float = 1.0,
    ) -> TTSResult:
        """POST /v1/text-to-speech/{voice_id} → wav bytes. Returns timing info."""
        out_path.parent.mkdir(parents=True, exist_ok=True)

        body = {
            "text": text,
            "language": language,
            "style": style,
            "model": model,
            "output_format": output_format,
            "voice_settings": {
                "pitch_shift": pitch_shift,
                "pitch_variance": pitch_variance,
                "speed": speed,
            },
        }
        url = f"/v1/text-to-speech/{voice_id}"
        log.info("Supertone TTS: voice=%s chars=%d model=%s", voice_id, len(text), model)
        with self._client.stream(
            "POST", url, json=body, headers={"Accept": "audio/wav, application/json"}
        ) as resp:
            if resp.status_code >= 400:
                # try to read error json
                body_text = resp.read().decode("utf-8", errors="replace")
                raise httpx.HTTPStatusError(
                    f"Supertone TTS failed {resp.status_code}: {body_text}",
                    request=resp.request,
                    response=resp,
                )
            out_path.write_bytes(resp.read())

        duration_ms = _wav_duration_ms(out_path)
        return TTSResult(
            audio_path=out_path,
            duration_ms=duration_ms,
            word_timings=estimate_word_timings(text, duration_ms),
            char_count=len(text),
        )


def _to_voice(v: dict[str, Any]) -> Voice:
    return Voice(
        id=str(v.get("voice_id") or v.get("id") or ""),
        name=str(v.get("name") or v.get("display_name") or ""),
        language=v.get("language"),
        gender=v.get("gender"),
        style=v.get("style"),
        age=v.get("age"),
        use_case=v.get("use_case"),
        raw=v,
    )


def _wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate() or 1
            return int(frames * 1000 / rate)
    except wave.Error:
        # not a standard wav (e.g. mp3) — fall back to ffprobe
        return _ffprobe_duration_ms(path)


def _ffprobe_duration_ms(path: Path) -> int:
    import subprocess

    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return int(float(out.stdout.strip()) * 1000)
    except ValueError:
        return 0


def estimate_word_timings(text: str, total_duration_ms: int) -> list[WordTiming]:
    """Distribute words evenly across the audio duration, weighted by length.

    This is an approximation used when the TTS response does not include
    phoneme-level timings. Good enough for burn-in subtitles at MVP quality.
    For word-perfect timing, call the /stream endpoint with include_phonemes=true.
    """
    words = [w for w in text.split() if w.strip()]
    if not words or total_duration_ms <= 0:
        return []

    weights = [max(1, len(w)) for w in words]
    total_weight = sum(weights)
    cursor = 0
    timings: list[WordTiming] = []
    for w, weight in zip(words, weights):
        dur = int(total_duration_ms * weight / total_weight)
        timings.append(WordTiming(word=w, start_ms=cursor, end_ms=cursor + dur))
        cursor += dur
    # Absorb rounding drift into the last word.
    if timings:
        timings[-1].end_ms = total_duration_ms
    return timings


def parse_ndjson_phonemes(ndjson_bytes: bytes) -> list[dict]:
    """Parse NDJSON stream from /stream endpoint with include_phonemes=true.

    Each line is a JSON object with keys like {audio_base64, phonemes: [{symbol, start, duration}, ...]}.
    This helper is exposed for future precise timing; current client defaults to the simple endpoint.
    """
    out: list[dict] = []
    for line in ndjson_bytes.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
