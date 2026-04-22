from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class SourceIngestIn(BaseModel):
    url: HttpUrl
    run_analysis: bool = True


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    idx: int
    start_ms: int
    end_ms: int
    thumb_path: str | None


class TranscriptSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    hook_text: str | None
    hook_type: str | None
    product_category: str | None
    cta_text: str | None
    tone: str | None
    style_notes: str | None
    structure_json: list


class SourceVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    platform: str
    url: str
    caption: str | None
    local_path: str | None
    duration_sec: float | None
    width: int | None
    height: int | None
    view_count: int | None
    like_count: int | None
    posted_at: datetime | None
    status: str
    error: str | None


class SourceVideoDetailOut(SourceVideoOut):
    segments: list[TranscriptSegmentOut] = []
    scenes: list[SceneOut] = []
    analysis: AnalysisOut | None = None
