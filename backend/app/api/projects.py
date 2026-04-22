"""Projects & renders API."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.core.events import bus
from app.models import Product, Project, Render, Script, SourceVideo, TTSAsset, VideoAnalysis
from app.schemas.project import (
    ProjectIn,
    ProjectOut,
    RenderIn,
    RenderOut,
    ScriptOut,
)
from app.services.analyzer.analyzer import AnalyzedSegment, VideoAnalysisResult
from app.services.composer import BrollClip, ComposeSpec, SegmentInput, render_reel
from app.services.scripter import ProductBrief, ScriptRequest, generate_script
from app.services.subtitle import SubtitleStyle
from app.services.tts import SupertoneClient

router = APIRouter()


@router.get("", response_model=list[ProjectOut])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return session.query(Project).order_by(Project.id.desc()).all()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, session: Session = Depends(get_session)) -> Project:
    p = Project(
        name=body.name,
        product_id=body.product_id,
        target_duration_sec=body.target_duration_sec,
        reference_video_ids_json=body.reference_video_ids,
        tone=body.tone,
        must_include_json=body.must_include,
        avoid_json=body.avoid,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.post("/{project_id}/generate-script", response_model=ScriptOut)
def generate_project_script(project_id: int, session: Session = Depends(get_session)) -> Script:
    proj = session.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    product = session.get(Product, proj.product_id) if proj.product_id else None

    refs: list[VideoAnalysisResult] = []
    for sv_id in proj.reference_video_ids_json:
        sv = session.get(SourceVideo, sv_id)
        if not sv:
            continue
        va = session.query(VideoAnalysis).filter(VideoAnalysis.source_video_id == sv.id).first()
        if not va:
            continue
        refs.append(
            VideoAnalysisResult(
                hook_text=va.hook_text or "",
                hook_type=va.hook_type or "other",
                cta_text=va.cta_text or "",
                product_category=va.product_category or "",
                tone=va.tone or "",
                style_notes=va.style_notes or "",
                structure=[AnalyzedSegment(**s) for s in (va.structure_json or [])],
            )
        )

    brief = ProductBrief(
        name=product.name if product else "Unknown product",
        brand=product.brand if product else None,
        price=product.price if product else None,
        description=product.description if product else None,
        features=list(product.features_json) if product else [],
        target_audience=product.target_audience if product else None,
        cta_url=product.cta_url if product else None,
    )
    draft = generate_script(
        ScriptRequest(
            product=brief,
            references=refs,
            target_duration_sec=proj.target_duration_sec,
            tone=proj.tone,
            must_include=list(proj.must_include_json),
            avoid=list(proj.avoid_json),
        )
    )

    latest = (
        session.query(Script)
        .filter(Script.project_id == proj.id)
        .order_by(Script.version.desc())
        .first()
    )
    version = (latest.version + 1) if latest else 1
    s = Script(
        project_id=proj.id,
        version=version,
        segments_json=[asdict(seg) for seg in draft.segments],
        total_chars=draft.total_chars,
        created_by="claude",
    )
    session.add(s)
    proj.status = "scripted"
    session.commit()
    session.refresh(s)
    return s


@router.post("/{project_id}/render", response_model=RenderOut, status_code=202)
def render_project(
    project_id: int,
    body: RenderIn,
    bg: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Render:
    proj = session.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    script = session.get(Script, body.script_id)
    if not script or script.project_id != proj.id:
        raise HTTPException(400, "script does not belong to project")

    settings = get_settings()
    output = settings.renders_dir / f"project-{proj.id}-script-{script.id}.mp4"
    r = Render(
        project_id=proj.id,
        script_id=script.id,
        output_path=str(output),
        width=settings.render_width,
        height=settings.render_height,
        duration_sec=0,
        params_json={"voice_id": body.voice_id, "bgm_path": body.bgm_path},
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    bg.add_task(_render_background, r.id, body.voice_id, body.bgm_path)
    return r


def _render_background(render_id: int, voice_id: str, bgm_path: str | None) -> None:
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        r = session.get(Render, render_id)
        if not r:
            return
        proj = session.get(Project, r.project_id)
        script = session.get(Script, r.script_id)
        settings = get_settings()
        try:
            # TTS per segment
            tts_work = settings.tts_dir / f"script-{script.id}"
            tts_work.mkdir(parents=True, exist_ok=True)
            tts_assets: list[TTSAsset] = []
            with SupertoneClient() as client:
                for i, seg in enumerate(script.segments_json):
                    out_wav = tts_work / f"seg_{i:03d}.wav"
                    res = client.synthesize(
                        seg["text"], voice_id=voice_id, out_path=out_wav
                    )
                    asset = TTSAsset(
                        script_id=script.id,
                        segment_index=i,
                        audio_path=str(out_wav),
                        word_timings_json=[w.__dict__ for w in res.word_timings],
                        duration_ms=res.duration_ms,
                    )
                    session.add(asset)
                    tts_assets.append(asset)
                session.commit()

            # B-roll: use first reference video's entire track as fallback
            proj_refs = list(proj.reference_video_ids_json or [])
            broll_source: Path | None = None
            if proj_refs:
                sv = session.get(SourceVideo, proj_refs[0])
                if sv and sv.local_path:
                    broll_source = Path(sv.local_path)

            segments_input = []
            for seg, asset in zip(script.segments_json, tts_assets):
                broll = None
                if broll_source and asset.duration_ms > 0:
                    broll = BrollClip(
                        source_path=broll_source,
                        in_ms=0,
                        out_ms=asset.duration_ms,
                    )
                segments_input.append(
                    SegmentInput(
                        tts_audio_path=Path(asset.audio_path),
                        tts_duration_ms=asset.duration_ms,
                        text=seg["text"],
                        emphasis_words=list(seg.get("emphasis_words") or []),
                        broll=broll,
                    )
                )

            result = render_reel(
                ComposeSpec(
                    segments=segments_input,
                    output_path=Path(r.output_path),
                    work_dir=settings.renders_dir / f"work-{r.id}",
                    width=r.width,
                    height=r.height,
                    fps=settings.render_fps,
                    bgm_path=Path(bgm_path) if bgm_path else None,
                    subtitle_style=SubtitleStyle(video_width=r.width, video_height=r.height),
                )
            )
            r.duration_sec = result.duration_ms / 1000.0
            proj.status = "rendered"
            session.commit()
            _publish(r.project_id, "render.done", {"render_id": r.id, "output": r.output_path})
        except Exception as e:  # noqa: BLE001
            r.error = str(e)
            session.commit()
            _publish(r.project_id, "render.failed", {"render_id": r.id, "error": str(e)})
    finally:
        session.close()


def _publish(project_id: int, type_: str, payload: dict) -> None:
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(bus.publish(f"project:{project_id}", type_, payload), loop)
        else:
            asyncio.run(bus.publish(f"project:{project_id}", type_, payload))
    except RuntimeError:
        asyncio.run(bus.publish(f"project:{project_id}", type_, payload))
