---
title: Finnie — Demo Video Deliverable
story: 10.2
---

# Demo video (Story 10.2)

Submission requirement [PS §5]: a **5–10 minute** video showing Finnie’s main features for evaluators who will not run the app first.

## Video link

| Field | Value |
|---|---|
| **URL** | _Add after recording (YouTube unlisted, Drive, LMS, etc.)_ |
| **Duration** | _mm:ss (must be 5:00–10:00)_ |
| **Recorded** | _YYYY-MM-DD_ |
| **Recorder** | _Name_ |

## Story 10.2 acceptance checklist

| # | Criterion | Shown in video? |
|---|---|---|
| 1 | Length 5–10 minutes | |
| 2 | Multi-turn chat with **different agents** | |
| 3 | **Portfolio analysis** (chat upload and/or Portfolio tab) | |
| 4 | **Market data** (chat and/or Markets tab) | |
| 5 | **Goal planning** example | |
| 6 | Agents **working together** across turns (e.g. tax follow-up after goal/Roth) | |
| 7 | At least one **advice disclaimer** (D-7) | |
| 8 | At least one **freshness label** (D-24) | |
| 9 | Recorded with **cache/mock fallback** available so limits do not break the demo (AC 4) | |

## How to record

1. Follow [`demo-video-script.md`](demo-video-script.md) (timed shot list and narration).
2. Pre-flight: [`uat-script.md`](uat-script.md) or `pytest -k uat --cov-fail-under=0`.
3. **Avoid API limit failures on camera:**
   - Prefer a warm session (run one market question before recording), **or**
   - Set `MARKET_DATA_MODE=mock` in `.env` and restart for labeled **Sample data** throughout, **or**
   - Record soon after a fresh day’s Alpha Vantage quota.
4. Tooling: OS screen recorder (QuickTime, OBS, etc.); capture browser at http://localhost:8501; 1280×720 or 1920×1080.

## Files

| File | Purpose |
|---|---|
| [`demo-video-script.md`](demo-video-script.md) | What to show and say, minute by minute |
| [`uat-script.md`](uat-script.md) | Full functional checklist before recording |

When the URL is filled in above, Story 10.2 is ready for submission alongside the codebase.
