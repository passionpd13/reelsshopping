"""Claude-powered script generator for new shopping reels.

Inputs: target product + references (analyzed patterns from existing reels).
Output: a structured script with role-labeled segments ready for TTS and composition.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from app.core.llm import get_llm
from app.core.logging import get_logger
from app.services.analyzer.analyzer import SEGMENT_ROLES, VideoAnalysisResult

log = get_logger(__name__)


@dataclass
class ProductBrief:
    name: str
    brand: str | None = None
    price: str | None = None
    description: str | None = None
    features: list[str] = field(default_factory=list)
    target_audience: str | None = None
    cta_url: str | None = None


@dataclass
class ScriptSegment:
    index: int
    role: str
    text: str
    duration_hint_ms: int
    broll_query: list[str] = field(default_factory=list)
    overlay: dict | None = None
    emphasis_words: list[str] = field(default_factory=list)


@dataclass
class ScriptDraft:
    target_duration_sec: int
    segments: list[ScriptSegment]

    @property
    def total_chars(self) -> int:
        return sum(len(s.text) for s in self.segments)

    def to_json(self) -> dict:
        return {
            "target_duration_sec": self.target_duration_sec,
            "segments": [asdict(s) for s in self.segments],
        }


@dataclass
class ScriptRequest:
    product: ProductBrief
    references: list[VideoAnalysisResult]
    target_duration_sec: int = 30
    tone: str = "energetic"
    must_include: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)


SYSTEM_PROMPT = """당신은 한국 쇼핑 릴스 대본 작가입니다.
상품 정보와 참고 릴스 분석을 바탕으로 새로운 30초 내외의 쇼핑 릴스 대본을 만듭니다.

출력은 반드시 유효한 JSON 하나이며 다음 스키마를 따릅니다:
{{
  "target_duration_sec": int,
  "segments": [
    {{
      "index": int,
      "role": one of {roles},
      "text": string,        // 한국어, 자연스러운 구어체, 쉼표/줄바꿈 없이 한 문장 단위
      "duration_hint_ms": int,
      "broll_query": [string, ...],  // 해당 구간에 어울리는 b-roll 검색어(영문 가능)
      "overlay": null | {{ "type": "product_card"|"cta_button", "text": string }},
      "emphasis_words": [string, ...] // 자막에서 강조할 핵심 단어
    }}
  ]
}}

규칙:
- 후킹(hook)은 첫 3초 안에 강력한 한 줄.
- 총 재생시간이 target_duration_sec ± 2초에 맞도록 text 길이와 duration_hint_ms 합을 조정.
- 한국어 TTS 가독성을 위해 한 세그먼트 text는 25자 내외.
- must_include 키워드는 자연스럽게 포함, avoid 키워드는 사용 금지.
- cta는 마지막 세그먼트에 반드시 1개.
- 마크다운/설명/코드펜스 없이 JSON만 출력.
"""


def _refs_to_context(refs: list[VideoAnalysisResult]) -> str:
    if not refs:
        return "(참고 영상 없음)"
    blocks = []
    for i, r in enumerate(refs, 1):
        blocks.append(
            f"[참고{i}] hook_type={r.hook_type} tone={r.tone} category={r.product_category}\n"
            f"  hook: {r.hook_text}\n"
            f"  cta: {r.cta_text}\n"
            f"  style: {r.style_notes}\n"
            f"  structure: " + " | ".join(f"{s.role}: {s.text}" for s in r.structure)
        )
    return "\n\n".join(blocks)


def _product_to_context(p: ProductBrief) -> str:
    lines = [f"상품명: {p.name}"]
    if p.brand:
        lines.append(f"브랜드: {p.brand}")
    if p.price:
        lines.append(f"가격: {p.price}")
    if p.description:
        lines.append(f"설명: {p.description}")
    if p.features:
        lines.append("핵심 특징:\n- " + "\n- ".join(p.features))
    if p.target_audience:
        lines.append(f"타겟: {p.target_audience}")
    return "\n".join(lines)


def generate_script(req: ScriptRequest) -> ScriptDraft:
    llm = get_llm()
    system = SYSTEM_PROMPT.format(roles=SEGMENT_ROLES)

    user_msg = (
        f"[상품]\n{_product_to_context(req.product)}\n\n"
        f"[참고 릴스 분석]\n{_refs_to_context(req.references)}\n\n"
        f"[요구사항]\n"
        f"- target_duration_sec: {req.target_duration_sec}\n"
        f"- tone: {req.tone}\n"
        f"- must_include: {', '.join(req.must_include) or '(없음)'}\n"
        f"- avoid: {', '.join(req.avoid) or '(없음)'}\n"
    )

    log.info("Generating script for product=%s duration=%ds", req.product.name, req.target_duration_sec)
    resp = llm.client.messages.create(
        model=llm.model,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    return _parse_script(raw)


def revise_script(current: ScriptDraft, instruction: str) -> ScriptDraft:
    """Apply a free-form user instruction to an existing script draft."""
    llm = get_llm()
    system = SYSTEM_PROMPT.format(roles=SEGMENT_ROLES)

    user_msg = (
        f"[현재 대본 JSON]\n{json.dumps(current.to_json(), ensure_ascii=False)}\n\n"
        f"[수정 지시]\n{instruction}\n\n"
        "현재 대본을 수정 지시에 맞게 업데이트한 전체 JSON을 다시 출력하세요."
    )
    resp = llm.client.messages.create(
        model=llm.model,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    return _parse_script(raw)


def _parse_script(raw: str) -> ScriptDraft:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json\n"):
            s = s[5:]
        s = s.rsplit("```", 1)[0]
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        lo, hi = s.find("{"), s.rfind("}")
        data = json.loads(s[lo : hi + 1])

    segments = [
        ScriptSegment(
            index=seg.get("index", i),
            role=seg.get("role", "feature"),
            text=seg.get("text", ""),
            duration_hint_ms=int(seg.get("duration_hint_ms", 3000)),
            broll_query=list(seg.get("broll_query") or []),
            overlay=seg.get("overlay"),
            emphasis_words=list(seg.get("emphasis_words") or []),
        )
        for i, seg in enumerate(data.get("segments", []))
    ]
    return ScriptDraft(
        target_duration_sec=int(data.get("target_duration_sec", 30)),
        segments=segments,
    )
