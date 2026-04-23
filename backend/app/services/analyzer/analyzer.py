"""Claude-powered analysis of a reference reel's transcript.

Produces a structured breakdown: hook text/type, scene roles, CTA, tone.
Segment role enum is shared with the scripter so pattern transfer is consistent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.core.llm import get_llm
from app.core.logging import get_logger
from app.services.ingestor.stt import STTResult

log = get_logger(__name__)

SEGMENT_ROLES = [
    "hook",
    "problem",
    "solution",
    "feature",
    "social_proof",
    "product_reveal",
    "cta",
]

HOOK_TYPES = [
    "curiosity_gap",
    "bold_claim",
    "question",
    "pain_point",
    "before_after",
    "listicle",
    "shock",
    "other",
]


@dataclass
class AnalyzedSegment:
    role: str
    text: str
    start_ms: int
    end_ms: int


@dataclass
class VideoAnalysisResult:
    hook_text: str
    hook_type: str
    cta_text: str
    product_category: str
    tone: str
    style_notes: str
    structure: list[AnalyzedSegment] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "hook_text": self.hook_text,
            "hook_type": self.hook_type,
            "cta_text": self.cta_text,
            "product_category": self.product_category,
            "tone": self.tone,
            "style_notes": self.style_notes,
            "structure": [seg.__dict__ for seg in self.structure],
        }


SYSTEM_PROMPT = """당신은 한국 쇼핑 숏폼(릴스/틱톡) 카피라이터 분석가입니다.
전사된 대본과 세그먼트 타임스탬프를 받아 다음을 JSON으로 출력하세요:

- hook_text: 첫 3~5초 후킹 문구(원문 그대로).
- hook_type: {hook_types} 중 하나.
- cta_text: 마지막 CTA(call-to-action) 원문. 없으면 빈 문자열.
- product_category: 예) "뷰티/스킨케어", "패션/여성의류", "주방/조리기구" 등.
- tone: "energetic" | "calm" | "informative" | "humorous" | "aspirational".
- style_notes: 말투/편집 특징을 한국어 2~3문장으로.
- structure: 전사 세그먼트 각각을 {roles} 중 하나의 role로 라벨링하여 배열로 반환.
  각 원소는 {{role, text, start_ms, end_ms}}. 순서 유지.

반드시 유효한 JSON만 출력. 마크다운, 코드펜스, 설명 금지.
"""


def _build_user_message(stt: STTResult) -> str:
    lines = [f"[{s.start_ms}-{s.end_ms}] {s.text}" for s in stt.segments]
    return (
        f"언어: {stt.lang}\n"
        f"전체 대본:\n{stt.full_text}\n\n"
        f"세그먼트({len(stt.segments)}개):\n" + "\n".join(lines)
    )


def analyze_transcript(stt: STTResult) -> VideoAnalysisResult:
    llm = get_llm()
    system = SYSTEM_PROMPT.format(
        hook_types=", ".join(HOOK_TYPES),
        roles=", ".join(SEGMENT_ROLES),
    )

    log.info("Analyzing transcript (%d segments) with %s", len(stt.segments), llm.model)
    resp = llm.client.messages.create(
        model=llm.model,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": _build_user_message(stt)}],
    )

    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    data = _extract_json(raw)

    structure = [
        AnalyzedSegment(
            role=seg.get("role", "feature"),
            text=seg.get("text", ""),
            start_ms=int(seg.get("start_ms", 0)),
            end_ms=int(seg.get("end_ms", 0)),
        )
        for seg in data.get("structure", [])
    ]

    return VideoAnalysisResult(
        hook_text=data.get("hook_text", ""),
        hook_type=data.get("hook_type", "other"),
        cta_text=data.get("cta_text", ""),
        product_category=data.get("product_category", ""),
        tone=data.get("tone", "informative"),
        style_notes=data.get("style_notes", ""),
        structure=structure,
    )


def _extract_json(raw: str) -> dict:
    """Best-effort JSON parse; strip accidental code fences."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json\n"):
            s = s[5:]
        s = s.rsplit("```", 1)[0]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # retry: find first { ... last }
        lo, hi = s.find("{"), s.rfind("}")
        if lo >= 0 and hi > lo:
            return json.loads(s[lo : hi + 1])
        raise
