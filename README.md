# Finnie: AI Finance Assistant

*Democratizing financial literacy through intelligent conversational AI.*

Finnie is a multi-agent conversational tutor that helps beginners learn to invest. Six specialist agents work behind a single chat interface. They explain concepts in plain language, analyze an uploaded portfolio, look up market data, plan savings goals, summarize financial news and explain US tax-advantaged accounts.

> **Status: planning.** The product requirements document is final (v1.0). Implementation has not started yet. Setup and usage instructions will be added as the code is built.

> **Disclaimer:** Finnie is an educational project. Nothing it produces is professional financial or tax advice. Any advice-type response it gives will carry a disclaimer.

## The problem

Most adults want to invest but are blocked by jargon, too many choices and fear of making mistakes. Human financial advisors are expensive and have account minimums. Generic robo-advisors push products without teaching the underlying concepts. As a result, many people leave money in low-yield savings accounts instead of building wealth.

## What Finnie will do

### Six specialist agents

| Agent | What it does |
|---|---|
| Finance Q&A | Explains concepts like compound interest or ETFs vs. mutual funds, citing a curated knowledge base |
| Portfolio Analysis | Analyzes uploaded holdings: total value, allocation, expense ratios, diversification and risk |
| Market Analysis | Looks up quotes and recent trends and explains what the numbers mean |
| Goal Planning | Calculates how much to save each month to reach a target, based on the user's risk tolerance |
| News Synthesizer | Summarizes current financial news with sources |
| Tax Education | Explains US accounts such as 401(k), IRA and Roth |

A LangGraph router reads each question and sends it to the right agent. The conversation keeps its context for the session, so follow-up questions can move between agents.

### Four tabs

- **Chat:** the conversation, showing which agent answered, its sources and data freshness labels
- **Portfolio:** upload holdings as a CSV (`ticker`, `shares`, optional `expense_ratio`) and see metrics and charts
- **Markets:** quotes and trend charts for 3–5 configured tickers, plus a ticker lookup
- **Goals:** a savings-goal form with a projection chart

### Built for trust

- Answers from the knowledge base cite their sources.
- Every market and news figure is labeled **Live**, **Cached** or **Sample data**.
- Advice-type responses always include a disclaimer.
- The app keeps working when an API is down or out of requests, falling back to cached or labeled sample data.

## Tech stack

| Area | Choice |
|---|---|
| Agent orchestration | LangGraph, LangChain |
| LLM | OpenAI `gpt-4o-mini` (set with `OPENAI_MODEL`) |
| Vector store | FAISS |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| UI | Streamlit |
| Language | Python, async throughout |

### External services

| Service | Purpose | Free-tier limit |
|---|---|---|
| OpenAI API | LLM for all agents | Provided by the program |
| Alpha Vantage | Market data | 25 requests/day, 5/minute |
| SerpApi | News search | 100 requests/month |
| Tavily | News search (optional) | 1,000 requests/month |

Because these limits are tight, Finnie caches results (30 minutes for quotes, 24 hours for daily price history, 6 hours for news) and falls back to cached or labeled sample data.

## Scope (v1)

- **In scope:** all six agents, the four tabs, US markets and accounts only, local deployment, at least 80% test coverage.
- **Out of scope:** user accounts or saved profiles (everything lasts for the session only), cloud hosting, the optional MCP server, and the Future Directions list in the PRD (for example, mobile apps, voice and automated investing).

## Planned project structure

```
ai_finance_assistant/
├── src/
│   ├── agents/
│   ├── core/
│   ├── data/
│   ├── rag/
│   ├── web_app/
│   ├── utils/
│   └── workflow/
├── tests/
├── config.yaml
├── requirements.txt
└── README.md
```

## Documentation

- [`docs/prd.md`](docs/prd.md): the product requirements document, including requirements, 10 epics with stories and acceptance criteria, and the log of all product decisions
- [`docs/sources/`](docs/sources/): the source documents the PRD was built from

## Roadmap

The work is planned as 10 epics, built in this order:

1. Research & architecture, ending with a runnable app skeleton
2. Knowledge base: 50–100 articles, a glossary and sample portfolios
3. RAG system
4. Real-time data: Alpha Vantage, SerpApi, caching and fallbacks
5. Core agents: Finance Q&A, Portfolio Analysis, Market Analysis
6. Workflow orchestration: router, session state and personalization
7. Advanced agents: Goal Planning, News Synthesizer, Tax Education
8. User interface
9. Testing & QA
10. Documentation & deployment

See [`docs/prd.md`](docs/prd.md) §5–§6 for the details.
