from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "env": s.app_env,
        "data_dir": str(s.data_dir),
        "whisper_model": s.whisper_model,
        "has_anthropic_key": bool(s.anthropic_api_key),
        "has_supertone_key": bool(s.supertone_api_key),
    }
