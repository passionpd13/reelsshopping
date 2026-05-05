# reels-search (PoC A)

Image → product video. The first and riskiest piece of the reelsshopping
pipeline: given a product photo (e.g. a Coupang screenshot), find the same
product's video on Taobao / 1688 / Douyin and download it locally.

```
image  ──► Gemini Vision ──► {keywords_zh, category, color, ...}
            │
            ▼
       parallel search ──► [taobao, alibaba1688, douyin, serpapi]
            │
            ▼
   pHash rank vs image ──► top K candidates
            │
            ▼
       yt-dlp download ──► downloads/*.mp4
```

## Setup

Requires Python 3.11+, [uv](https://github.com/astral-sh/uv), and `ffmpeg` on
PATH (used by yt-dlp for muxing).

```bash
cd services/api
uv sync
cp .env.example .env
# edit .env and set GEMINI_API_KEY at minimum
```

## Run

```bash
# Step 1: just see what Gemini extracts from your image
uv run reels-search keywords /path/to/product.jpg

# Step 2: full pipeline — search, rank, download
uv run reels-search find /path/to/product.jpg
```

Downloaded videos land in `./downloads/` by default (override with
`DOWNLOAD_DIR`).

## Tunables (.env)

| var | purpose |
| --- | --- |
| `GEMINI_API_KEY` | Required. Used by `vision.py` to extract keywords. |
| `SERPAPI_KEY` | Optional. Reliable fallback when direct scraping is blocked. |
| `TAOBAO_COOKIE` / `ALIBABA1688_COOKIE` / `DOUYIN_COOKIE` | Raw `Cookie:` header values copied from a logged-in browser. Without these, anti-bot pages will degrade results. |
| `SEARCH_PLATFORMS` | Comma list, e.g. `taobao,alibaba1688,douyin,serpapi`. |
| `MAX_CANDIDATES_PER_PLATFORM` | Search result cap before ranking. |
| `MAX_RESULTS` | How many videos to actually download. |

## Honest limitations of this PoC

- **Direct platform scraping is fragile.** Taobao especially gates non-logged-
  in HTML. The adapters parse what they can and the pipeline auto-falls back
  to SerpAPI when results are empty. For production, expect to either supply
  cookies from a real session or replace these with a paid scraping service
  (Apify, ScraperAPI, Bright Data) or headless-browser based fetching.
- **Douyin** SSR layout changes often. The current parser is best-effort and
  `yt-dlp` is the actual download workhorse once we have a video page URL.
- **Ranking** uses pHash on the thumbnail. For higher recall on visually
  similar but differently-cropped products, swap `rank.py` to CLIP image
  embeddings (e.g. `open_clip` ViT-B/32). The interface is already a single
  function so this is a drop-in change.

## Project layout

```
services/api/src/reels_search/
├── cli.py            # typer CLI entrypoint
├── config.py         # pydantic-settings, .env
├── models.py         # ProductQuery, SearchCandidate, VideoResult
├── vision.py         # Gemini image -> ProductQuery
├── search/
│   ├── base.py       # SearchAdapter ABC
│   ├── taobao.py
│   ├── alibaba1688.py
│   ├── douyin.py
│   └── serpapi.py
├── download.py       # video URL extraction + yt-dlp
├── rank.py           # pHash similarity ranking
└── pipeline.py       # orchestrator
```

## Next milestones

Once search recall is acceptable on real products, we'll move on to:

- **B**: Electron desktop shell with the 4-step UI from the reference video.
- **C**: Gemini scene/cut analysis + script generation.
- **D**: Supertone TTS sync + ffmpeg subtitle burn-in.
- **E**: LAN HTTP server + QR for phone delivery.
