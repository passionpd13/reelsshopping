"""Sources API — reference reels ingested from URL.

Users paste Instagram / TikTok URLs; the backend downloads, transcribes,
detects scenes, and (optionally) runs Claude analysis. All heavy work is
fire-and-forget via BackgroundTasks; the endpoint returns immediately with
the row id and `status`. Progress updates flow on /events/{id} (SSE).
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.db import get_session
from app.core.events import bus
from app.core.logging import get_logger
from app.models import Scene, SourceVideo, Transcript, TranscriptSegment, VideoAnalysis
from app.schemas.source import (
    AnalysisOut,
    SceneOut,
    SourceIngestIn,
    SourceVideoDetailOut,
    SourceVideoOut,
    TranscriptSegmentOut,
)
from app.services.analyzer import analyze_transcript
from app.services.collector import download_url, platform_from_url
from app.services.ingestor import ingest
from app.services.ingestor.stt import STTResult, STTSegment

router = APIRouter()
log = get_logger(__name__)


@router.get("", response_model=list[SourceVideoOut])
def list_sources(session: Session = Depends(get_session)) -> list[SourceVideo]:
    return session.query(SourceVideo).order_by(SourceVideo.id.desc()).all()


@router.get("/{source_id}", response_model=SourceVideoDetailOut)
def get_source(source_id: int, session: Session = Depends(get_session)) -> SourceVideoDetailOut:
    sv = session.get(SourceVideo, source_id)
    if not sv:
        raise HTTPException(404, "not found")
    segs = (
        session.query(TranscriptSegment)
        .join(Transcript, Transcript.id == TranscriptSegment.transcript_id)
        .filter(Transcript.source_video_id == sv.id)
        .order_by(TranscriptSegment.start_ms)
        .all()
    )
    scenes = session.query(Scene).filter(Scene.source_video_id == sv.id).order_by(Scene.idx).all()
    analysis = session.query(VideoAnalysis).filter(VideoAnalysis.source_video_id == sv.id).first()
    return SourceVideoDetailOut(
        **SourceVideoOut.model_validate(sv).model_dump(),
        segments=[TranscriptSegmentOut.model_validate(s) for s in segs],
        scenes=[SceneOut.model_validate(s) for s in scenes],
        analysis=AnalysisOut.model_validate(analysis) if analysis else None,
    )


@router.post("", response_model=SourceVideoOut, status_code=202)
def create_source(
    body: SourceIngestIn,
    bg: BackgroundTasks,
    session: Session = Depends(get_session),
) -> SourceVideo:
    existing = session.query(SourceVideo).filter(SourceVideo.url == str(body.url)).first()
    if existing:
        bg.add_task(_process_source, existing.id, body.run_analysis)
        return existing

    sv = SourceVideo(platform=platform_from_url(str(body.url)), url=str(body.url), status="pending")
    session.add(sv)
    session.commit()
    session.refresh(sv)
    bg.add_task(_process_source, sv.id, body.run_analysis)
    return sv


@router.get("/{source_id}/events")
async def source_events(source_id: int) -> EventSourceResponse:
    async def gen():
        async for evt in bus.subscribe(f"source:{source_id}"):
            yield {"event": evt.type, "data": evt.to_sse()}

    return EventSourceResponse(gen())


# ----------------------------------------------------------------------
# Background pipeline
# ----------------------------------------------------------------------
def _process_source(source_id: int, run_analysis: bool) -> None:
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        sv = session.get(SourceVideo, source_id)
        if sv is None:
            return
        _publish(source_id, "download.start", {})
        try:
            dl = download_url(sv.url)
        except Exception as e:  # noqa: BLE001
            sv.status = "failed"
            sv.error = f"download: {e}"
            session.commit()
            _publish(source_id, "download.failed", {"error": str(e)})
            return

        sv.platform = dl.platform
        sv.platform_video_id = dl.platform_video_id
        sv.caption = dl.caption
        sv.posted_at = dl.posted_at
        sv.view_count = dl.view_count
        sv.like_count = dl.like_count
        sv.local_path = str(dl.local_path)
        sv.duration_sec = dl.duration_sec
        sv.width, sv.height = dl.width, dl.height
        sv.status = "downloaded"
        session.commit()
        _publish(source_id, "download.done", {"local_path": sv.local_path})

        _publish(source_id, "ingest.start", {})
        try:
            ig = ingest(dl.local_path)
        except Exception as e:  # noqa: BLE001
            sv.status = "failed"
            sv.error = f"ingest: {e}"
            session.commit()
            _publish(source_id, "ingest.failed", {"error": str(e)})
            return

        t = Transcript(source_video_id=sv.id, lang=ig.stt.lang, full_text=ig.stt.full_text)
        session.add(t)
        session.flush()
        for s in ig.stt.segments:
            session.add(
                TranscriptSegment(
                    transcript_id=t.id,
                    start_ms=s.start_ms,
                    end_ms=s.end_ms,
                    text=s.text,
                    confidence=s.confidence,
                )
            )
        for sc in ig.scenes:
            session.add(
                Scene(
                    source_video_id=sv.id,
                    idx=sc.idx,
                    start_ms=sc.start_ms,
                    end_ms=sc.end_ms,
                    thumb_path=str(sc.thumb_path) if sc.thumb_path else None,
                )
            )
        sv.status = "ingested"
        session.commit()
        _publish(source_id, "ingest.done",
                 {"segments": len(ig.stt.segments), "scenes": len(ig.scenes)})

        if not run_analysis:
            return

        _publish(source_id, "analyze.start", {})
        try:
            stt = STTResult(
                lang=ig.stt.lang,
                full_text=ig.stt.full_text,
                segments=[STTSegment(s.start_ms, s.end_ms, s.text, s.confidence) for s in ig.stt.segments],
            )
            result = analyze_transcript(stt)
        except Exception as e:  # noqa: BLE001
            sv.status = "failed"
            sv.error = f"analyze: {e}"
            session.commit()
            _publish(source_id, "analyze.failed", {"error": str(e)})
            return

        va = VideoAnalysis(
            source_video_id=sv.id,
            hook_text=result.hook_text,
            hook_type=result.hook_type,
            product_category=result.product_category,
            cta_text=result.cta_text,
            tone=result.tone,
            style_notes=result.style_notes,
            structure_json=[seg.__dict__ for seg in result.structure],
        )
        session.add(va)
        sv.status = "analyzed"
        session.commit()
        _publish(source_id, "analyze.done", result.to_json())
    finally:
        session.close()


def _publish(source_id: int, type_: str, payload: dict) -> None:
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(bus.publish(f"source:{source_id}", type_, payload), loop)
        else:
            asyncio.run(bus.publish(f"source:{source_id}", type_, payload))
    except RuntimeError:
        asyncio.run(bus.publish(f"source:{source_id}", type_, payload))
