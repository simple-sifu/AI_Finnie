# Finnie: AI Finance Assistant

*Democratizing financial literacy through intelligent conversational AI.*

Finnie is a multi-agent conversational tutor that helps beginners learn to invest. Six specialist agents work behind a single chat interface. They explain concepts in plain language, analyze an uploaded portfolio, look up market data, plan savings goals, summarize financial news and explain US tax-advantaged accounts.

> **Status: v1 prototype ready for local evaluation.** All six agents, four tabs, tests and benchmarks are implemented. See [Usage examples](#usage-examples) to try Finnie after setup.

> **Disclaimer:** Finnie is an educational project. Nothing it produces is professional financial or tax advice. Any advice-type response it gives will carry a disclaimer.

## The problem

Most adults want to invest but are blocked by jargon, too many choices and fear of making mistakes. Human financial advisors are expensive and have account minimums. Generic robo-advisors push products without teaching the underlying concepts. As a result, many people leave money in low-yield savings accounts instead of building wealth.

## What Finnie does

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

## Architecture overview

Finnie is a **single Streamlit app** backed by a **LangGraph workflow** and **six agents**. The Chat tab sends each question through a router that picks one agent; Portfolio, Markets and Goals call agents directly because the tab already implies the task.

```text
User → Streamlit tabs → async runner → LangGraph (validate → route → agent → finalize)
                                              ↓
                         OpenAI (router + agent) · FAISS retrieval · Alpha Vantage · SerpApi
```

- **Session state only:** conversation history and profile live in the browser session (no database).
- **Trust layer:** every path through the graph passes `finalize`, which applies disclaimers on advice and freshness labels on market/news figures.
- **Resilience:** disk cache, request budgets and labeled sample data when APIs are down or over limit.

Full diagrams, agent protocols, RAG details and NFR13 notes: [`docs/architecture.md`](docs/architecture.md). Technology rationale: [`docs/technology-choices.md`](docs/technology-choices.md).

## Development setup

**Prerequisites:** Python 3.12 and git. Python 3.12 specifically, because some dependencies (PyTorch, FAISS) may not support newer versions.

```bash
# 1. Clone the repository
git clone https://github.com/simple-sifu/AI_Finnie.git
cd AI_Finnie

# 2. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install the pinned dependencies (includes PyTorch, so this can take a few minutes)
pip install --upgrade pip
pip install -r requirements.txt

# 4. Add your API keys
cp .env.example .env             # then edit .env and fill in the keys
python -m src.core.config        # checks the configuration; prints "Configuration OK"

# 5. Run the tests with coverage
pytest

# 6. Start the app (opens at http://localhost:8501)
streamlit run src/web_app/app.py
```

`pytest` reports test coverage and fails if it drops below 80% (PRD D-13). Tests never use your real API keys.

### Docker (optional)

With [Docker](https://docs.docker.com/get-docker/) installed and `.env` configured:

```bash
docker compose up --build
```

Then open http://localhost:8501. API keys come from `.env`; runtime cache is stored in a Docker volume. See [`docs/deployment.md`](docs/deployment.md) for `docker run` and the full artifact checklist (Story 10.3).

### Running the tests

```bash
pytest                     # all tests, with a coverage report
pytest tests/unit          # just the unit tests: about 20 seconds, fully offline
```

- **Coverage:** `pytest` fails if line coverage drops below 80% (it is about 99%).
- **Unit tests make no real API calls.** A guard in `tests/unit/conftest.py` watches every outside network connection and fails any test that tries one. They use mocks, sample data and fixed seeds, and they do not need your API keys or a `.env` file.
- **Integration tests** (`tests/integration`, about 30 seconds) send questions through the whole real stack: the router, the agents, the real knowledge-base search with the real embedding model, the data clients, caches and request budgets, and the real OpenAI client. Only the outside services' answers are faked (a small fake OpenAI server on your machine, plus fake Alpha Vantage and SerpApi responses), so they cost nothing. They are offline by default: any attempt to reach a real service fails the test. The embedding model is downloaded once (about 90 MB).
- **Optional live tests** call the real services and are skipped unless you ask for them:

```bash
RUN_LIVE_SMOKE=1 pytest -m live tests/integration/test_live_smoke.py -s   # one request to each service, 3 in all
RUN_LIVE_TESTS=1 pytest -m live -s                                        # longer checks with the real model (a few cents)
```

Both need the keys in your `.env`. A service that reports its daily limit as reached still counts as reachable in the smoke test.

- **User acceptance (Story 9.3):** the PM script is in [`docs/uat-script.md`](docs/uat-script.md); record runs in [`docs/uat-results.md`](docs/uat-results.md). `pytest -k uat --cov-fail-under=0` checks the same demo scenarios offline (about 30 seconds).
- **Performance (Story 9.4):** `python scripts/benchmark.py` measures NFR13 targets and updates [`docs/benchmarks.md`](docs/benchmarks.md) (about 10 seconds, offline fakes).

### Configuration

- **API keys** go in `.env`, which is never committed. You need `OPENAI_API_KEY`, `ALPHA_VANTAGE_API_KEY` and `SERPAPI_API_KEY`. `TAVILY_API_KEY` is only needed if you switch the news provider to Tavily.
- **Settings** are in `config.yaml`: model, cache times, tickers, limits and the disclaimer text.
- **Overrides:** environment variables win over `config.yaml`. `OPENAI_MODEL`, `MARKET_DATA_MODE` (`live` or `mock`) and `QUOTE_CACHE_TTL_SECONDS` have their own names. Any other setting can be overridden with `FINNIE_<SECTION>__<KEY>`, for example `FINNIE_MARKET__DAILY_LIMIT=10`.

If a required key is missing, the app shows which one instead of starting.

## API and configuration

### External APIs

| API | Used for | Authentication | Notes |
|---|---|---|---|
| OpenAI Chat Completions | Router + all agents | `OPENAI_API_KEY` | Structured JSON outputs per agent; model from `OPENAI_MODEL` (default `gpt-4o-mini`) |
| Alpha Vantage | Quotes and daily history | `ALPHA_VANTAGE_API_KEY` | `GLOBAL_QUOTE` and `TIME_SERIES_DAILY`; budgets in `config.yaml` `market:` |
| SerpApi Google News | News headlines | `SERPAPI_API_KEY` | Default provider; set `news.provider: tavily` and `TAVILY_API_KEY` to switch |
| Hugging Face (download only) | Embedding model for RAG | none for public model | First index build or test run downloads `all-MiniLM-L6-v2` (~90 MB) |

Finnie does **not** expose its own HTTP API; evaluators run the Streamlit app locally.

### Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | LLM |
| `ALPHA_VANTAGE_API_KEY` | yes | Market data |
| `SERPAPI_API_KEY` | yes* | News (*unless using Tavily) |
| `TAVILY_API_KEY` | if Tavily | Alternate news provider |
| `OPENAI_MODEL` | no | Overrides `llm.model` in `config.yaml` |
| `MARKET_DATA_MODE` | no | `live` (default) or `mock` for labeled sample prices |
| `QUOTE_CACHE_TTL_SECONDS` | no | Quote cache TTL (default 1800) |
| `FINNIE_<SECTION>__<KEY>` | no | Any `config.yaml` setting, e.g. `FINNIE_MARKET__DAILY_LIMIT=10` |

See [`.env.example`](.env.example). Validate keys with `python -m src.core.config`.

### Main `config.yaml` sections

| Section | Controls |
|---|---|
| `llm` | Model, temperature, timeouts, retries |
| `chat` | History length, input size, answer timeout |
| `router` | Minimum routing confidence |
| `rag` | Chunk size, top-k, minimum similarity score |
| `market` / `news` | Tickers, cache TTLs, API budgets, provider |
| `goals` | Assumed annual returns by risk level |
| `portfolio` | Max upload rows (200) and file size (1 MB) |
| `disclaimer` | Text shown on advice-type answers |

## Usage examples

After [setup](#development-setup), open **http://localhost:8501**.

### Chat (multi-agent)

Try these in order in one session to see routing and context:

1. `What is an ETF?` → Finance Q&A with **Sources**
2. `How is VTI doing?` → Market Analysis with a **Live** / **Cached** / **Sample data** label
3. `I want $20,000 in 4 years for a house. I have $3,000 saved.` → Goal Planning asks for risk tolerance; answer **moderate** in the sidebar or chat
4. Upload `src/data/samples/diversified.csv` with `Is my portfolio diversified?` → Portfolio Analysis

The full PM script is in [`docs/uat-script.md`](docs/uat-script.md).

### Portfolio tab

Upload a CSV with columns `ticker`, `shares`, optional `expense_ratio`. Start with [`src/data/samples/diversified.csv`](src/data/samples/diversified.csv). Use **Refresh prices** if some rows show sample or stale data after an API limit.

### Markets tab

View configured tickers (default SPY, QQQ, DIA, VTI, BND) and use the lookup box for another symbol (for example `AAPL`).

### Goals tab

Enter a target amount, current savings, timeline and risk level to see a monthly savings estimate and chart (with disclaimer).

## Troubleshooting

| Problem | What to do |
|---|---|
| App says a key is missing | Copy `.env.example` → `.env` and fill in the three required keys; run `python -m src.core.config` |
| `Configuration OK` fails | Check for typos in variable names; keys must not be empty strings |
| Finance Q&A or Tax unavailable | Knowledge index missing or corrupt — run `python -m src.rag.build_index` |
| Test fails on “index stale” | Content changed — rebuild the index (same command) |
| Market/news shows **Sample data** | Expected when `MARKET_DATA_MODE=mock`, daily limit hit, or provider error; app stays usable |
| Alpha Vantage limit during demo | Set `MARKET_DATA_MODE=mock` in `.env` and restart, or rely on cache from an earlier load |
| Slow first chat answer | First run loads the embedding model; later turns are faster (see [`docs/benchmarks.md`](docs/benchmarks.md)) |
| `pytest` fails on network | Unit/integration tests should stay offline; do not proxy-block localhost or Hugging Face on first run |
| OpenAI errors in chat | Check key and quota; router retries then shows a friendly message (Story 5.3) |

### Knowledge base index

Finnie's articles and glossary are searched through a FAISS index stored in `src/data/index/` and committed to the repo, so it works right after cloning. After editing anything in `src/data/articles/` or `src/data/glossary.yaml`, or the `rag:` settings, rebuild it:

```bash
python -m src.rag.build_index    # no API keys needed; first run downloads a ~90 MB model
```

A test fails if the content has changed without a rebuild.

## Accessibility and design

- Branded as **Finnie**, using Streamlit's default theme. There is no custom branding beyond the name.
- **Color is never the only signal.** Data freshness labels use a word as well as a colored dot (Live, Cached, Sample data), price moves use an arrow and a sign (▲ +1.2%, ▼ -0.5%), and every value is printed on the charts.
- Every chart has a title, labeled axes or a legend, and plain-language labels, and a **Show as table** switch that shows the same data as a table.
- The layout works at laptop and tablet widths. On narrow screens the metric tiles and ticker cards wrap two to a row.
- **No formal accessibility standard (such as WCAG) is targeted in v1**, and the app has not been audited against one.

## Sample data

Sample portfolios for testing and the demo are in [`src/data/samples/`](src/data/samples/). Holdings files are CSVs with the columns `ticker`, `shares` and an optional `expense_ratio`, written as a percentage (`0.03` means 0.03%).

| File | What it shows |
|---|---|
| `diversified.csv` | A spread across US and international stock funds, bonds, real estate and one stock |
| `concentrated.csv` | Most of the money in two individual stocks |
| `missing_expense_ratios.csv` | Some funds without an expense ratio, to test the built-in fee table |
| `malformed_missing_column.csv` | Error case: no `shares` column |
| `malformed_bad_values.csv` | Error cases: a non-numeric share count, a missing ticker, negative shares and a non-numeric expense ratio |

## Project structure

The repository root is the `ai_finance_assistant/` folder from the prescribed structure:

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
├── scripts/             # benchmark.py (NFR13)
├── docs/
├── Dockerfile           # local container (Story 10.3)
├── docker-compose.yml
├── config.yaml
├── requirements.txt
├── .env.example
└── README.md
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md): technical design — system overview, agent protocols, RAG, performance (Story 1.3 / 10.1)
- [`docs/front-end-spec.md`](docs/front-end-spec.md): Streamlit UI specification
- [`docs/technology-choices.md`](docs/technology-choices.md): why each major technology was chosen (Story 10.1)
- [`docs/prd.md`](docs/prd.md): product requirements, epics and decision log
- [`docs/uat-script.md`](docs/uat-script.md) and [`docs/uat-results.md`](docs/uat-results.md): user acceptance script and results (Story 9.3)
- [`docs/benchmarks.md`](docs/benchmarks.md): NFR13 performance benchmarks (Story 9.4)
- [`docs/demo-video-script.md`](docs/demo-video-script.md) and [`docs/demo-video.md`](docs/demo-video.md): demo recording script and submission link checklist (Story 10.2)
- [`docs/deployment.md`](docs/deployment.md): deployment artifacts and Docker instructions (Story 10.3)
- [`docs/sources/`](docs/sources/): source documents the PRD was built from

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
