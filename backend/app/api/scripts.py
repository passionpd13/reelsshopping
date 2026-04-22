"""Scripts API — read, revise (via Claude), and manual edit."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models import Script
from app.schemas.project import ScriptOut, ScriptReviseIn
from app.services.scripter import ScriptDraft, ScriptSegment, revise_script

router = APIRouter()


@router.get("/{script_id}", response_model=ScriptOut)
def get_script(script_id: int, session: Session = Depends(get_session)) -> Script:
    s = session.get(Script, script_id)
    if not s:
        raise HTTPException(404, "not found")
    return s


@router.post("/{script_id}/revise", response_model=ScriptOut)
def ai_revise(
    script_id: int, body: ScriptReviseIn, session: Session = Depends(get_session)
) -> Script:
    s = session.get(Script, script_id)
    if not s:
        raise HTTPException(404, "not found")
    draft = ScriptDraft(
        target_duration_sec=30,  # Claude will respect what's in the payload
        segments=[ScriptSegment(**seg) for seg in s.segments_json],
    )
    new_draft = revise_script(draft, body.instruction)

    new_script = Script(
        project_id=s.project_id,
        version=s.version + 1,
        segments_json=[asdict(seg) for seg in new_draft.segments],
        total_chars=new_draft.total_chars,
        created_by="claude",
    )
    session.add(new_script)
    session.commit()
    session.refresh(new_script)
    return new_script


@router.patch("/{script_id}", response_model=ScriptOut)
def manual_edit(
    script_id: int, segments: list[dict], session: Session = Depends(get_session)
) -> Script:
    """User-edited segments create a new version (append-only)."""
    s = session.get(Script, script_id)
    if not s:
        raise HTTPException(404, "not found")
    new_script = Script(
        project_id=s.project_id,
        version=s.version + 1,
        segments_json=segments,
        total_chars=sum(len(seg.get("text", "")) for seg in segments),
        created_by="user",
    )
    session.add(new_script)
    session.commit()
    session.refresh(new_script)
    return new_script
