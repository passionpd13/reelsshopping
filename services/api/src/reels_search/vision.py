"""Gemini Vision: image -> structured product query.

Why this matters: Taobao/1688/Douyin search recall is dramatically higher when
queried in Chinese with the right category words. Asking the user for keywords
defeats the "paste image and forget" UX, so we let Gemini do it.
"""

from pathlib import Path

from google import genai
from google.genai import types

from .config import settings
from .models import ProductQuery

_PROMPT = """You are a product search assistant for a Korean shopping-video tool.

Given the product image, output a JSON object describing the item so we can
search for it on Taobao (淘宝), 1688 (阿里巴巴), and Douyin (抖音).

Rules:
- keywords_zh: 3-6 Simplified Chinese terms a Chinese seller would use in a
  product title. Order from most specific to most generic. Avoid brand names
  unless clearly visible. Include the category noun (e.g. 马桶刷, 拖把头).
- keywords_en / keywords_ko: same idea in English / Korean.
- category: one short Chinese category phrase (e.g. "一次性马桶刷").
- color: dominant product color in Chinese, or "" if unclear.
- distinguishing_features: 2-4 short Chinese phrases describing material,
  shape, or function visible in the image (e.g. "可拆卸刷头", "长杆设计").

Output ONLY the JSON. No prose.
"""


def _client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return genai.Client(api_key=settings.gemini_api_key)


def _mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")


def extract_query(image_path: Path) -> ProductQuery:
    """Run Gemini Vision on an image file and return a structured ProductQuery."""

    image_bytes = image_path.read_bytes()
    client = _client()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=_mime_for(image_path)),
            _PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ProductQuery,
            temperature=0.2,
        ),
    )

    parsed = response.parsed
    if isinstance(parsed, ProductQuery):
        return parsed
    # Fallback: parse from text if SDK didn't auto-deserialize
    return ProductQuery.model_validate_json(response.text)
