from pydantic import BaseModel, ConfigDict


class ProjectIn(BaseModel):
    name: str
    product_id: int | None = None
    target_duration_sec: int = 30
    reference_video_ids: list[int] = []
    tone: str = "energetic"
    must_include: list[str] = []
    avoid: list[str] = []


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    product_id: int | None
    target_duration_sec: int
    reference_video_ids_json: list[int]
    tone: str
    must_include_json: list[str]
    avoid_json: list[str]
    status: str


class ScriptSegmentDTO(BaseModel):
    index: int
    role: str
    text: str
    duration_hint_ms: int
    broll_query: list[str] = []
    overlay: dict | None = None
    emphasis_words: list[str] = []


class ScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    version: int
    segments_json: list
    voice_id: str | None
    total_chars: int
    estimated_cost: float
    created_by: str


class ScriptReviseIn(BaseModel):
    instruction: str


class RenderIn(BaseModel):
    script_id: int
    voice_id: str
    bgm_path: str | None = None


class RenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    script_id: int
    output_path: str
    duration_sec: float
    width: int
    height: int
    error: str | None
