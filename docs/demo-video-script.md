---
title: Finnie — Demo Video Recording Script
story: 10.2
status: final
target_duration: 7–8 minutes
---

# Demo video script (Story 10.2)

Use this script to record a **5–10 minute** submission video that satisfies [PS §5](sources/project-brief-finnie.md) and Story 10.2 AC. It mirrors the UAT demo flow ([`uat-script.md`](uat-script.md)) but is **timed for recording** and calls out what must appear on screen.

**Before you record:** run through [`uat-script.md`](uat-script.md) once (or `pytest -k uat --cov-fail-under=0`). See [`demo-video.md`](demo-video.md) for setup and the link checklist.

## Pre-recording setup (off camera)

1. Fresh terminal: `streamlit run src/web_app/app.py` → http://localhost:8501
2. Sidebar: **Knowledge level** = Beginner (default is fine)
3. **New conversation** so the session is clean
4. Have `src/data/samples/diversified.csv` and `concentrated.csv` ready
5. **Safe demo mode (recommended):** if you are near API limits, set `MARKET_DATA_MODE=mock` in `.env` and restart — labels will show **Sample data** (Story 10.2 AC 4). Otherwise use live keys; caching will help on repeat lookups.

---

## On-camera script

| Time | Where | What you do | What evaluators must see |
|---|---|---|---|
| **0:00–0:45** | Chat | Introduce Finnie: six agents, one chat, four tabs. Mention educational purpose and disclaimers on advice. | App title, four tabs, sidebar profile |
| **0:45–1:30** | Chat | Ask: `What is an ETF?` | **Finance Q&A** badge; **Sources** expanded; no disclaimer (education) |
| **1:30–2:15** | Chat | Ask: `How is VTI doing?` | **Market Analysis**; price/trend; freshness label with word **Live**, **Cached**, or **Sample data** (AC 3) |
| **2:15–3:15** | Chat | Ask: `I want $20,000 in 4 years for a house. I have $3,000 saved.` then answer **`moderate`** when asked | **Goal Planning**; monthly savings figure; **disclaimer** callout under answer (AC 3); sidebar **Risk tolerance** = Moderate |
| **3:15–4:00** | Chat | Ask: `Would I owe taxes if I take money out of my Roth early?` | **Tax Education**; **Sources**; answer references earlier context (goal/Roth) — **agents working together** (D-16, FAQ Sub 3) |
| **4:00–4:45** | Chat | Ask: `What's in the financial news today?` | **News**; publisher names; freshness label on news |
| **4:45–5:45** | Chat | Upload **`diversified.csv`** with: `Is my portfolio diversified?` | **Portfolio Analysis**; total value; labels on prices |
| **5:45–6:30** | Portfolio | Open **Portfolio** tab; upload **`diversified.csv`** again if needed | Metrics, charts, holdings table with **Data** column labels |
| **6:30–7:15** | Markets | Open **Markets** tab | Ticker cards, change arrows, freshness labels; optional lookup `SPY` |
| **7:15–8:00** | Goals | Enter target **$20,000**, savings **$3,000**, **4** years, **Moderate** | Projection chart; monthly amount; **disclaimer** on plan |
| **8:00–8:30** | Chat | **New conversation** → upload **`concentrated.csv`**, ask `Analyze my portfolio` | Advice-style answer; **disclaimer** (AC 3) if not already shown clearly |
| **8:30–9:00** | Any | One sentence on trust: sources, labels, fallbacks if APIs limit out | Optional: mention cache/mock; wrap submission |

Adjust pacing to stay **under 10 minutes**. If running long, shorten intros and skip the optional Markets lookup.

## Narration tips

- Speak in plain language; let the UI show agent badges and labels.
- Pause briefly after each answer so disclaimers and **Sources** are readable.
- Do not read API keys or `.env` on screen.

## After recording

1. Export **MP4** (1080p recommended)
2. Upload (course LMS, YouTube unlisted, Google Drive, etc.)
3. Paste the public or unlisted URL in [`demo-video.md`](demo-video.md)
4. Confirm duration with a host or player timestamp (5–10 minutes)
