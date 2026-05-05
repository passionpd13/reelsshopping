from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["taobao", "alibaba1688", "douyin", "serpapi", "mock"]


class ProductQuery(BaseModel):
    """Structured product info extracted from an input image by Gemini Vision.

    Keywords are produced in both Chinese (for native platform search) and
    English/Korean (for fallback). Categories help disambiguate when the same
    keywords map to multiple unrelated product types.
    """

    keywords_zh: list[str] = Field(default_factory=list, description="Chinese keywords")
    keywords_en: list[str] = Field(default_factory=list, description="English keywords")
    keywords_ko: list[str] = Field(default_factory=list, description="Korean keywords")
    category: str = ""
    color: str = ""
    distinguishing_features: list[str] = Field(default_factory=list)

    def primary_query(self, lang: Literal["zh", "en", "ko"] = "zh") -> str:
        bag = {"zh": self.keywords_zh, "en": self.keywords_en, "ko": self.keywords_ko}[lang]
        if not bag:
            return ""
        return " ".join(bag[:5])


class SearchCandidate(BaseModel):
    """A product page candidate that may have a video."""

    platform: Platform
    title: str
    product_url: str
    thumbnail_url: str | None = None
    # Pre-extracted video URL if the search result already exposes one.
    video_url: str | None = None
    raw_score: float = 0.0  # platform-native ranking signal, if any


class VideoResult(BaseModel):
    """A downloaded video plus the metadata used to find/rank it."""

    candidate: SearchCandidate
    local_path: Path
    similarity: float = 0.0  # perceptual-hash similarity to the query image, [0, 1]
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
