---
title: Finnie — Technology Choices and Reasoning
story: 10.1
status: final
---

# Technology choices (FAQ Submission 2)

This document explains **why** Finnie uses each major technology. Details of how they fit together are in [`architecture.md`](architecture.md).

| Choice | Why this one |
|---|---|
| **Python 3.12** | Matches the prescribed stack; PyTorch, FAISS and sentence-transformers are tested on 3.12 for this project (D-6, architecture §4). |
| **LangGraph + LangChain** | Required orchestration pattern (D-2). A single router → one agent → `finalize` graph keeps latency predictable (NFR13) and makes routing testable with structured outputs (architecture §6). |
| **OpenAI `gpt-4o-mini`** | Program-provided API key; strong enough for six agents at low cost (D-6). Model name is configurable via `OPENAI_MODEL`. |
| **FAISS + `all-MiniLM-L6-v2`** | Local retrieval with no embedding API cost; index ships in the repo so evaluators need no extra setup (D-2, Story 6.1). |
| **Streamlit** | Required UI (D-4); four tabs and chat map cleanly to the PRD without custom front-end work, so effort stays on agents and workflow (FAQ Sub 1). |
| **Alpha Vantage** | Required live market data source (D-2); free tier is tight, so caching, budgets and labeled sample fallbacks are first-class (Epic 8). |
| **SerpApi (Tavily optional)** | News search within free limits (D-10, D-14); same cache-and-fallback pattern as market data. |
| **httpx + asyncio** | Async HTTP for data clients (D-17); a background event loop bridges Streamlit’s sync model to async agents (architecture §10). |
| **Pydantic** | Structured router and agent outputs, settings and API models—easier to test than parsing free text (architecture §7). |
| **pytest + 80% coverage gate** | Required quality bar (D-13); unit tests stay offline; integration tests use fakes for external APIs (Epic 9). |
| **YAML + `.env` configuration** | Non-secret defaults in `config.yaml`; secrets only in `.env` (D-25, Story 1.5). |

## What we did not use (and why)

| Alternative | Reason skipped |
|---|---|
| **yFinance** | Out of scope by decision D-2; Alpha Vantage only for v1. |
| **Cloud hosting / auth** | Local deployment only (D-20); session state in Streamlit, no user accounts (D-15). |
| **Crew-style multi-agent chatter** | One agent per user question (D-16) to control cost and latency. |
| **MCP / Claude Desktop** | Epic 11 stretch; not built in v1 (D-28). |

See [`docs/prd.md`](prd.md) Appendix B for the full decision log.
