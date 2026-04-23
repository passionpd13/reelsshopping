from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    s = get_settings()
    provider = (s.llm_provider or "anthropic").lower()
    if provider == "vertex":
        llm_ready = bool(s.vertex_project_id) and (
            bool(s.google_application_credentials) or True  # ADC fallback allowed
        )
        llm_model = s.vertex_model
    else:
        llm_ready = bool(s.anthropic_api_key)
        llm_model = s.anthropic_model
    return {
        "ok": True,
        "env": s.app_env,
        "data_dir": str(s.data_dir),
        "whisper_model": s.whisper_model,
        "llm": {
            "provider": provider,
            "model": llm_model,
            "ready": llm_ready,
            "vertex_project_id": s.vertex_project_id if provider == "vertex" else None,
            "vertex_region": s.vertex_region if provider == "vertex" else None,
        },
        "has_supertone_key": bool(s.supertone_api_key),
    }
