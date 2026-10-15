# Source: Project Brief — Finnie (verbatim)

*Provided by the user in chat on 2026-10-14. Saved verbatim as a PRD source; cited in `docs/prd.md` as [PB].*

---

Project 1 — Finnie: AI Finance
Assistant

Customer Problem
Most adults want to invest but are blocked by jargon, paralyzed by choices, and
afraid of making mistakes. Human financial advisors don't scale to beginners —
they're expensive and have account minimums. Generic robo-advisors push
products without teaching the underlying concepts. The result: millions of people
leave money in low-yield savings accounts instead of building wealth, because
the on-ramp into investing is intimidating and lonely.
Proposed Solution
A multi-agent conversational tutor that meets beginners where they are. Six
specialist agents collaborate behind a single chat interface:
● Finance Q&A Agent — explains concepts like compound interest, ETFs vs
mutual funds.
● Portfolio Analysis Agent — analyzes uploaded holdings for diversification
and risk.
● Market Analysis Agent — pulls live quotes and explains what the numbers
mean.
● Goal Planning Agent — calculates how much to save monthly to hit a target.
● News Synthesizer Agent — summarizes current financial news with
sources.
● Tax Education Agent — explains 401(k) vs IRA vs Roth without giving tax
advice.
A LangGraph router classifies each query and dispatches it to the right agent. RAG
over a 50-100 article knowledge base grounds answers in verified content. A
Streamlit UI ties it together with tabs for Chat, Portfolio, Markets, Goals, and

Knowledge. The system explicitly distinguishes education from advice and adds
disclaimers — a real regulatory concern in fintech.
Tech Stack
LangGraph, LangChain, OpenAI (or Google Gemini as a free alternative), FAISS
vector store, sentence-transformers (all-MiniLM-L6-v2) for embeddings, Streamlit
UI, async Python throughout.
External APIs & Services Required
Service Purpose Notes
OpenAI API LLM for all agents Provided by the program

Alpha Vantage Live market data

Free: 25 req/day, 5 req/min
— students sign up
themselves

SerpApi or Tavily News search

Free: SerpApi 100/mo,
Tavily 1,000/mo —
students sign up
themselves

Heads up: Alpha Vantage's 25-req/day cap is tight. Students must build
aggressive caching (30-min TTL) and mock data fallbacks early — this is the #1
demo killer.
Difficulty: Medium
A complete reference implementation is provided. Good starting project for
students who want to learn multi-agent patterns and RAG without too much
infrastructure overhead.
