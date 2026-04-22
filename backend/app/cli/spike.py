"""Phase 0 end-to-end spike.

Exercises the whole pipeline without the database or web UI:

    URL → download → STT → scene cut → Claude analyze → Claude script
        → Supertone TTS per segment → ASS subtitles → ffmpeg compose → mp4

Usage
-----
    python -m app.cli.main spike \\
        --url "https://www.tiktok.com/@xxx/video/123" \\
        --product-name "상품명" --product-price "29,000원" \\
        --duration 30
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.analyzer import analyze_transcript
from app.services.collector import download_url
from app.services.composer import BrollClip, ComposeSpec, SegmentInput, render_reel
from app.services.ingestor import ingest
from app.services.scripter import ProductBrief, ScriptRequest, generate_script
from app.services.subtitle import SubtitleStyle
from app.services.tts import SupertoneClient

log = get_logger(__name__)
console = Console()


def run(
    url: str = typer.Option(..., "--url", help="Reference reel URL (Instagram/TikTok)"),
    product_name: str = typer.Option(..., "--product-name"),
    product_price: str | None = typer.Option(None, "--product-price"),
    product_desc: str | None = typer.Option(None, "--product-desc"),
    product_features: str | None = typer.Option(None, "--product-features", help="세미콜론으로 구분"),
    target_audience: str | None = typer.Option(None, "--target-audience"),
    duration: int = typer.Option(30, "--duration", help="Target seconds"),
    tone: str = typer.Option("energetic", "--tone"),
    must_include: str | None = typer.Option(None, "--must-include", help="쉼표 구분"),
    avoid: str | None = typer.Option(None, "--avoid", help="쉼표 구분"),
    voice_id: str | None = typer.Option(None, "--voice-id"),
    output: str = typer.Option("reel.mp4", "--output"),
    bgm: str | None = typer.Option(None, "--bgm", help="Optional BGM file path"),
    language: str = typer.Option("ko", "--language"),
) -> None:
    settings = get_settings()
    voice_id = voice_id or settings.supertone_default_voice_id
    if not voice_id:
        raise typer.BadParameter("--voice-id가 필요합니다 (또는 SUPERTONE_DEFAULT_VOICE_ID)")

    console.rule("[bold cyan]1/6 Download reference")
    dl = download_url(url)
    console.print(f"  saved: {dl.local_path}  ({dl.duration_sec}s, {dl.width}x{dl.height})")

    console.rule("[bold cyan]2/6 STT + scene cuts")
    ingested = ingest(dl.local_path, scenes_dir=settings.scenes_dir, language=language)
    console.print(f"  {len(ingested.stt.segments)} STT segments, {len(ingested.scenes)} scenes")
    console.print(Panel(ingested.stt.full_text[:400], title="transcript preview"))

    console.rule("[bold cyan]3/6 Analyze reference (Claude)")
    analysis = analyze_transcript(ingested.stt)
    console.print(
        f"  hook_type={analysis.hook_type} tone={analysis.tone} category={analysis.product_category}"
    )

    console.rule("[bold cyan]4/6 Generate new script (Claude)")
    product = ProductBrief(
        name=product_name,
        price=product_price,
        description=product_desc,
        features=[f.strip() for f in (product_features or "").split(";") if f.strip()],
        target_audience=target_audience,
    )
    script = generate_script(
        ScriptRequest(
            product=product,
            references=[analysis],
            target_duration_sec=duration,
            tone=tone,
            must_include=[m.strip() for m in (must_include or "").split(",") if m.strip()],
            avoid=[a.strip() for a in (avoid or "").split(",") if a.strip()],
        )
    )
    console.print(Panel(json.dumps(script.to_json(), ensure_ascii=False, indent=2),
                        title=f"script ({script.total_chars} chars)"))

    console.rule("[bold cyan]5/6 Supertone TTS per segment")
    work_dir = settings.tts_dir / f"spike-{dl.local_path.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)
    tts_results = []
    with SupertoneClient() as tts:
        for i, seg in enumerate(script.segments):
            out = work_dir / f"seg_{i:03d}.wav"
            r = tts.synthesize(seg.text, voice_id=voice_id, out_path=out, language=language)
            tts_results.append(r)
            console.print(f"  seg {i}: {r.duration_ms} ms, {r.char_count} chars → {out.name}")

    console.rule("[bold cyan]6/6 Compose final mp4 (ffmpeg)")
    brolls = _pick_brolls(dl.local_path, ingested.scenes, tts_results)
    segments_input = []
    for seg, tts_res, broll in zip(script.segments, tts_results, brolls):
        segments_input.append(
            SegmentInput(
                tts_audio_path=tts_res.audio_path,
                tts_duration_ms=tts_res.duration_ms,
                text=seg.text,
                emphasis_words=seg.emphasis_words,
                broll=broll,
            )
        )

    out_path = Path(output)
    render = render_reel(
        ComposeSpec(
            segments=segments_input,
            output_path=out_path,
            work_dir=settings.renders_dir / f"spike-{out_path.stem}",
            width=settings.render_width,
            height=settings.render_height,
            fps=settings.render_fps,
            bgm_path=Path(bgm) if bgm else None,
            subtitle_style=SubtitleStyle(
                video_width=settings.render_width, video_height=settings.render_height
            ),
        )
    )
    console.print(f"[bold green]✓ done[/]  {render.output_path}  ({render.duration_ms} ms)")


def _pick_brolls(source: Path, scenes, tts_results) -> list[BrollClip | None]:
    """Simple round-robin scene picking for MVP.

    Future: embed segment text + scene captions, pick by cosine similarity.
    """
    if not scenes:
        return [None] * len(tts_results)

    picked: list[BrollClip | None] = []
    order = list(scenes)
    random.shuffle(order)
    for i, tts in enumerate(tts_results):
        sc = order[i % len(order)]
        picked.append(BrollClip(source_path=source, in_ms=sc.start_ms, out_ms=sc.end_ms))
    return picked
