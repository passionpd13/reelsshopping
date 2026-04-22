# Shopping Reels Generator

팔로우한 Instagram / TikTok 계정의 레퍼런스 영상을 수집·분석해서, Supertone TTS
내레이션과 자막이 들어간 새로운 쇼핑 릴스 영상을 반자동으로 만드는 도구.

## 구조

```
backend/   FastAPI + 파이프라인 서비스 (Python 3.11)
frontend/  Next.js (React) UI
data/      로컬 아티팩트 (gitignored)
```

## 인간 개입 지점

1. **영상 큐레이션** — 다운로드한 레퍼런스 중 어떤 걸 참고할지 선택
2. **대본 확정** — Claude가 뽑은 초안을 사용자가 편집·승인
3. **최종 검수** — 렌더된 mp4 미리보기 후 다운로드/업로드

## 파이프라인

```
URL 입력 → yt-dlp 다운로드 → faster-whisper STT → PySceneDetect 씬 컷
      → Claude 분석(후킹/구조) → Claude 대본 생성 → 사용자 편집
      → Supertone TTS → ASS 자막 빌드 → ffmpeg 합성 → mp4
```

## 시작하기

### 사전 요구사항
- Python 3.11+
- Node.js 20+
- ffmpeg 6+
- Anthropic API 키, Supertone API 키

### 설치
```bash
cp .env.example .env         # 키 채우기
cd backend && pip install -e .
cd ../frontend && npm install
```

### Phase 0 E2E 스파이크 (CLI)
```bash
# URL 하나로 원본 → 대본 → TTS → 자막 mp4까지
python -m app.cli.spike \
  --url "https://www.tiktok.com/@xxx/video/123" \
  --product-name "상품명" \
  --product-price "29,000원" \
  --duration 30
```

### 개발 서버
```bash
# backend
uvicorn app.main:app --reload --port 8000
# frontend
npm run dev
```

## 설계 문서

- 모듈별 인터페이스: `backend/app/services/*/`
- 데이터 모델: `backend/app/models/`
- API 스펙: FastAPI 자동 문서 `http://localhost:8000/docs`

## 주의사항

- Instagram/TikTok 자동 업로드는 구현하지 않음 (ToS).
- 원본 음성·얼굴 재사용 금지. B-roll은 변형 필수 (크롭·속도·필터).
- 참고 영상 수집은 **사용자가 URL을 직접 붙여넣는 방식**만 지원.
