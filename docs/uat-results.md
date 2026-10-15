---
title: Finnie — User Acceptance Test Results
story: 9.3
---

# User acceptance test results (Story 9.3)

Results for the script in [`uat-script.md`](uat-script.md).

| Field | Value |
|---|---|
| **Run date** | 2026-10-15 |
| **Tester** | PM (Tommy Han) |
| **App version** | `main` (Epic 10 final polish, Story 10.4) |
| **Environment** | Local Streamlit; `.env` with program API keys |
| **Automated companion** | `pytest -k uat --cov-fail-under=0` — **Pass** (2026-10-15; re-run in `./scripts/final_check.sh` for Story 10.4) |

## Summary

| Section | Steps | Result |
|---|---|---|
| 1. Multi-turn chat (six agents) | UAT-CHAT-01 … 08 | **Pass** |
| 2. Portfolio analysis | UAT-PORT-01 … 03 | **Pass** |
| 3. Market data | UAT-MKT-01 … 03 | **Pass** |
| 4. Goal planning | UAT-GOAL-01 … 02 | **Pass** |
| 5. Advice disclaimers | UAT-DISC-01 … 03 | **Pass** |
| 6. Freshness labels | UAT-FRESH-01 … 03 | **Pass** |
| 7. API limits and fallbacks | UAT-LIMIT-01 … 03 | **Pass** (LIMIT-02/03 optional manual checks confirmed on prior runs) |

**Overall:** **Pass** — no blocking issues open.

## Issues log

| ID | Step | Severity | Description | Resolution |
|---|---|---|---|---|
| — | — | — | No issues recorded for this run. | — |

## Notes

- Multi-turn session matched the Story 4.4 / demo flow: all six agents answered in one session; goal planning captured **moderate** risk in the sidebar; tax and portfolio turns reflected earlier context.
- Advice disclaimers appeared on concentrated portfolio analysis, goal plans and tax “should I” questions; education answers (ETF, compound interest) had no disclaimer.
- Freshness labels always included the words **Live**, **Cached**, or **Sample data**, not color alone.
- Simulated Alpha Vantage daily limit (automated UAT) produced **Sample data · not real prices** and stopped further API calls for that session budget.

## Re-test record (blocking fixes)

| Date | Steps re-run | Result |
|---|---|---|
| — | — | No blocking issues required re-test. |
