---
title: Finnie — User Acceptance Test Script
story: 9.3
status: final
---

# User acceptance test script (Story 9.3)

This script lets the PM walk through the demo scenarios from [PS §5](sources/project-brief-finnie.md) before a submission or demo video. It covers multi-turn chat across agents, portfolio analysis, market data, goal planning, and the trust behaviors required by D-7 (advice disclaimers), D-24 (freshness labels) and Story 8.3 (API limits and fallbacks).

Record outcomes in [`uat-results.md`](uat-results.md). Mark any step **Fail** or **Blocked** with a short note. Blocking issues must be fixed and the affected steps re-run before sign-off (Story 9.3 AC 4).

## Before you start

| Item | Detail |
|---|---|
| Environment | Python 3.12, dependencies from `requirements.txt`, keys in `.env` (see README) |
| Start the app | `streamlit run src/web_app/app.py` → http://localhost:8501 |
| Sample portfolio | `src/data/samples/diversified.csv` (and optionally `concentrated.csv` for advice) |
| Time | About 25–35 minutes for the full script; sections can be run separately |
| Automated check | `pytest -k uat --cov-fail-under=0` runs the same scenarios offline (no API cost). Use it to confirm fixes after a blocking issue. |

**Tip for a safe demo:** caching and labeled sample data are already built in. If you are near an API daily limit, set `MARKET_DATA_MODE=mock` in `.env` and restart; market and news figures should show **Sample data** labels (Story 8.6).

## How to score each step

| Result | Meaning |
|---|---|
| **Pass** | What you see matches the expected result |
| **Fail** | Behavior differs; note what happened |
| **Blocked** | Could not complete the step (crash, missing tab, etc.) |

---

## 1. Multi-turn chat — six agents in one session

Use the **Chat** tab. Leave the sidebar profile at defaults unless a step says otherwise. Ask each question in order; wait for the full answer before the next.

| ID | You type | Expected result |
|---|---|---|
| UAT-CHAT-01 | `What is an ETF?` | **Finance Q&A** answers in plain language; **Sources** lists at least one knowledge-base article; no disclaimer (education). |
| UAT-CHAT-02 | `How is VTI doing?` | **Market Analysis** gives a price or trend; a freshness label appears (**Live**, **Cached**, or **Sample data** — word plus colored dot). |
| UAT-CHAT-03 | `I want $20,000 in 4 years for a house. I have $3,000 saved.` | **Goal Planning** asks for your **risk tolerance** (conservative / moderate / aggressive). |
| UAT-CHAT-04 | `moderate` | A monthly savings amount and assumed return; **disclaimer** callout under the answer; sidebar **Risk tolerance** shows **moderate**. |
| UAT-CHAT-05 | `Would I owe taxes if I take it out early?` | **Tax Education** answers using retirement/tax content; **Sources** visible; disclaimer if the answer is advice-type. |
| UAT-CHAT-06 | `What's in the financial news today?` | **News** summary with publisher names; freshness label on news data. |
| UAT-CHAT-07 | Upload `diversified.csv` with the message `Is my portfolio diversified?` | **Portfolio Analysis** uses your file; total value and allocation make sense; prices labeled **Live** / **Cached** / **Sample data**. |

**Session check (UAT-CHAT-08):** Open the tax or portfolio answer and confirm later agents “remember” earlier turns (for example, risk tolerance or VTI mentioned). No agent badge should be wrong for the question type.

---

## 2. Portfolio analysis — Chat and Portfolio tab

| ID | Action | Expected result |
|---|---|---|
| UAT-PORT-01 | **New conversation**, then upload `concentrated.csv` and ask `Analyze my portfolio` | Advice-style commentary on concentration; **disclaimer** callout with the configured text (see front-end spec §3.2). |
| UAT-PORT-02 | Open **Portfolio** tab; upload `diversified.csv` | **Total value**, **Weighted expense ratio**, holdings table, two charts (“What you own”, “Your mix of investments”); each row’s **Data** column shows a freshness label. |
| UAT-PORT-03 | Upload `malformed_bad_values.csv` | Clear error listing row problems; no metrics or charts until the file is fixed. |

---

## 3. Market data — Markets tab and chat

| ID | Action | Expected result |
|---|---|---|
| UAT-MKT-01 | Open **Markets** tab (fresh session or after cache warm-up) | Cards for configured tickers (SPY, QQQ, DIA, VTI, BND); each card shows price, change with arrow/sign, and a freshness label. |
| UAT-MKT-02 | Use the ticker lookup (e.g. `AAPL`) | Quote or friendly “couldn’t find” message; label on any price shown. |
| UAT-MKT-03 | In **Chat**, ask `How is SPY doing?` | **Market Analysis**; label on figures; explanation readable for a beginner. |

---

## 4. Goal planning — Goals tab

| ID | Action | Expected result |
|---|---|---|
| UAT-GOAL-01 | Open **Goals** tab; enter target **$20,000**, current savings **$3,000**, **4** years, risk **Moderate** | Projection chart and monthly savings figure; **disclaimer** on the plan. |
| UAT-GOAL-02 | Return to **Chat** and ask a follow-up about the same goal | Router still knows your profile risk from the sidebar if you set it in chat earlier. |

---

## 5. Advice disclaimers (D-7)

| ID | Action | Expected result |
|---|---|---|
| UAT-DISC-01 | Any advice-type chat answer (portfolio recommendation, goal plan, tax “should I…”) | Yellow/warning-style **disclaimer** block **below** the answer, separate from body text. |
| UAT-DISC-02 | Pure education (e.g. `What is compound interest?`) | No disclaimer callout. |
| UAT-DISC-03 | Sidebar **About Finnie** (collapsed) | Mentions educational use and that advice-type answers include a disclaimer. |

Default disclaimer text (configurable in `config.yaml`):

> This is general information for learning purposes, not personalized financial, investment or tax advice. Consider speaking with a licensed professional before making decisions.

---

## 6. Freshness labels (D-24)

| ID | Action | Expected result |
|---|---|---|
| UAT-FRESH-01 | First market or portfolio price load with live APIs | Label contains the word **Live** (not color alone). |
| UAT-FRESH-02 | Repeat the same market question within the cache window | **Cached** appears in the label with time context. |
| UAT-FRESH-03 | With `MARKET_DATA_MODE=mock` in `.env` (restart app), open **Markets** or ask for a quote | Label contains **Sample data**; prices are not presented as live. |

---

## 7. API limits and fallbacks (Story 8.3)

| ID | Action | Expected result |
|---|---|---|
| UAT-LIMIT-01 | **Automated:** `pytest -k uat_limit --cov-fail-under=0` | Passes: simulated Alpha Vantage daily limit → **Sample data** labels; no crash; further requests do not spam the API. |
| UAT-LIMIT-02 | **Manual (optional):** After UAT-LIMIT-01 passes, set `MARKET_DATA_MODE=mock`, restart, reload **Markets** | All cards show **Sample data**; app remains usable. |
| UAT-LIMIT-03 | **Manual (optional):** With live keys, if SerpApi or OpenAI fails, chat shows a friendly message (no stack trace). | Info-style message and a path forward (retry, rephrase). |

---

## Sign-off

When every step is **Pass** (or **Blocked** items are fixed and re-tested), complete the summary table in [`uat-results.md`](uat-results.md) and note the date and tester name.
