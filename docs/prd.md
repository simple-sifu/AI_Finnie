---
title: Finnie — AI Finance Assistant
status: final
created: 2026-10-14
updated: 2026-10-14
sources:
  - docs/sources/1_AIFinanceAssistant.pdf
  - docs/sources/1_AIFinanceAssistantFAQ.pdf
  - docs/sources/project-brief-finnie.md
---

# Finnie: AI Finance Assistant Product Requirements Document (PRD)

*Democratizing Financial Literacy Through Intelligent Conversational AI*

> **How to read this document.** This PRD maps the product manager's three source documents into the BMAD PRD structure. The source documents are the source of truth. Wording is kept from the source wherever possible. Every requirement carries a source tag so it can be traced back:
>
> - **[PS §n]** = `docs/sources/1_AIFinanceAssistant.pdf` (Problem Statement), section n (1 Business Use Case, 2 Technical Architecture, 3 Deliverables/Objectives, 4 Learning Goals, 5 Submission Guidelines, 6 Evaluation Criteria, 7 Future Directions)
> - **[MS n]** = `docs/sources/1_AIFinanceAssistantFAQ.pdf`, Core Milestone n
> - **[FAQ Area n]** = `docs/sources/1_AIFinanceAssistantFAQ.pdf`, FAQ question n in that area (Tech = Technical Implementation, Domain = Domain Knowledge, UI = User Interface, T&D = Testing & Documentation, Sub = Submission & Grading)
> - **[PB]** = Project Brief "Project 1 — Finnie: AI Finance Assistant" (`docs/sources/project-brief-finnie.md`, verbatim copy of the brief supplied 2026-10-14)
>
> Markers used:
> - `GAP-n`: BMAD needs this, the source does not provide it, and it has **not** been filled in. See §9.
> - `Q-n`: something in the source that looks unclear, contradictory or risky. It has **not** been changed. See §10.
> - `INTERP-n`: a place where mapping the source into BMAD required interpretation. See §11.
> - **Decision (D-n):** a PM decision recorded on top of the source wording. Source quotes are kept unchanged; the decision says which one applies. See §12.

---

## 1. Goals and Background Context

### 1.1 Goals

- Address the financial-literacy gap "by providing personalized, accessible financial education and guidance through an intelligent multi-agent conversational system." [PS §1]
- "A multi-agent conversational tutor that meets beginners where they are." [PB]
- **Democratized Financial Access:** "By providing clear, jargon-free explanations and personalized guidance, the assistant helps beginners overcome the intimidation factor of investing, potentially opening markets to millions of new participants." [PS §1]
- **Personalized Learning Paths:** "The multi-agent system adapts to each user's knowledge level, goals, and risk tolerance, creating customized educational experiences that traditional one-size-fits-all resources cannot match." [PS §1]
- **Real-Time Market Integration:** "By combining educational content with live market data, users can learn concepts while seeing real-world applications, bridging the gap between theory and practice." [PS §1]
- **Scalable Financial Guidance:** "The AI system can serve thousands of users simultaneously, providing quality financial education at a scale impossible with human advisors alone." [PS §1] **Decision D-20:** not a v1 requirement; v1 is deployed locally.
- "Develop a production-ready multi-agent financial assistant system." [PS §3] **Decision D-26:** "production-ready" means production-quality code that runs locally.
- "This project simulates a real-world fintech startup scenario where you're building an MVP to democratize financial education. Consider scalability, user trust, and regulatory compliance throughout your implementation." [PS §4]

### 1.2 Background Context

**Customer Problem** [PB]: "Most adults want to invest but are blocked by jargon, paralyzed by choices, and afraid of making mistakes. Human financial advisors don't scale to beginners — they're expensive and have account minimums. Generic robo-advisors push products without teaching the underlying concepts. The result: millions of people leave money in low-yield savings accounts instead of building wealth, because the on-ramp into investing is intimidating and lonely."

**Business Use Case** [PS §1]: "Financial literacy remains a significant barrier for millions of potential investors, with complex terminology, overwhelming choices, and fear of making mistakes preventing many from building wealth through investing. The AI Finance Assistant addresses this gap by providing personalized, accessible financial education and guidance through an intelligent multi-agent conversational system."

**Proposed Solution** [PB]: "Six specialist agents collaborate behind a single chat interface... A LangGraph router classifies each query and dispatches it to the right agent. RAG over a 50-100 article knowledge base grounds answers in verified content. A Streamlit UI ties it together with tabs for Chat, Portfolio, Markets, Goals, and Knowledge. The system explicitly distinguishes education from advice and adds disclaimers — a real regulatory concern in fintech."

**The Power of Multi-Agent LLMs** [PS §1]
- **Specialized Expertise:** Each agent focuses on specific domains (portfolio analysis, market trends, tax education), ensuring deep, accurate responses in each area.
- **Context Preservation:** The system maintains conversation history and user profiles, enabling progressively sophisticated guidance as users learn.
- **RAG Enhancement:** Retrieval-augmented generation ensures responses are grounded in verified financial knowledge while remaining conversational.

**Challenges and Considerations** [PS §1]
- **Regulatory Compliance:** The system must clearly distinguish between education and financial advice, including appropriate disclaimers.
- **Accuracy and Reliability:** Financial information must be accurate and up-to-date, with robust error handling for API failures.
- **User Trust:** Building confidence in AI-generated financial guidance requires transparency, citations, and conservative recommendations.

**Conclusion** [PS §1]: "The AI Finance Assistant represents a significant opportunity to democratize financial education, helping millions of beginners take their first steps toward financial security. By combining cutting-edge AI technology with sound financial principles, this system can transform how people learn about and engage with investing."

**Target users:** "Most adults [who] want to invest" and "beginners" [PB]; "beginners", "potential investors", "new participants" [PS §1]. No personas, segments or user journeys are defined. → `GAP-7`

**Target users (fills GAP-7; approved, D-40):** drawn from the [PB] Customer Problem. Both personas are US-based (D-21).
- **Maya, 26, first full-time job.** Has savings sitting in a low-yield savings account and a new employer 401(k). Has never invested and is put off by jargon and by fear of making a mistake. Uses Finnie to learn the basics (Finance Q&A), understand the 401(k) vs. an IRA or Roth (Tax Education), and plan a savings goal (Goal Planning).
- **Daniel, 38, a hesitant self-investor.** Has a 401(k) and a few stocks bought on tips, and isn't sure whether the portfolio is diversified or too risky. Uses Finnie to upload holdings (Portfolio Analysis), check prices and trends (Market Analysis), and understand current news (News Synthesizer).

**Non-users (v1; approved, D-40):** experienced traders looking for trading signals; users outside the US (D-21); financial advisors managing client accounts; anyone expecting Finnie to place trades (automated investing is out of scope, D-23).

**Difficulty / context** [PB]: "Difficulty: Medium. A complete reference implementation is provided. Good starting project for students who want to learn multi-agent patterns and RAG without too much infrastructure overhead." **Decision D-12:** the reference implementation is ignored; Finnie is built from scratch.

### 1.3 Learning Goals

*Placed here as project goals for the builder (see INTERP-4).* "This project provides hands-on experience with cutting-edge AI technologies while addressing a real-world problem:" [PS §4]

**Technical Skills**
- Master multi-agent architectures using LangChain and LangGraph/CrewAI
- Implement RAG systems with vector databases
- Build production-ready AI applications with proper error handling
- Integrate external APIs and manage real-time data
- Create intuitive user interfaces for AI systems

**Domain Knowledge**
- Understand basic financial concepts and investment principles
- Learn about portfolio management and diversification
- Grasp market dynamics and analysis techniques
- Appreciate regulatory and ethical considerations in fintech

**Professional Skills**
- Design complex systems with multiple interacting components
- Write comprehensive documentation and tests
- Consider user experience in AI application design
- Balance technical sophistication with accessibility

### 1.4 Change Log

| Date | Version | Description | Author |
|---|---|---|---|
| 2026-10-14 | 0.1 | Initial BMAD PRD mapped from the PM's source documents (`1_AIFinanceAssistant.pdf`, `1_AIFinanceAssistantFAQ.pdf`) | Claude (PM agent), for review |
| 2026-10-14 | 0.2 | Added the Finnie Project Brief as a third source [PB]; updated FRs, NFRs, technical assumptions, gaps and questions | Claude (PM agent), for review |
| 2026-10-14 | 0.3 | Recorded PM decisions D-1 to D-5 (Q-1, Q-4, Q-6, Q-18, Q-21) | Claude (PM agent), for review |
| 2026-10-14 | 0.4 | Recorded D-6 to D-8 (Q-10, Q-24, Q-25); updated D-4 (tab name "Markets") and D-5 (SerpApi and Tavily) | Claude (PM agent), for review |
| 2026-10-14 | 0.5 | Recorded D-9 (Q-26, partly); added Q-27 | Claude (PM agent), for review |
| 2026-10-14 | 0.6 | Recorded D-10 (Q-26) and D-11 (Q-27); added Q-28 | Claude (PM agent), for review |
| 2026-10-14 | 0.7 | Recorded D-12 (Q-20) | Claude (PM agent), for review |
| 2026-10-14 | 0.8 | Recorded D-13 to D-16 (Q-2, Q-28, Q-7, Q-22) | Claude (PM agent), for review |
| 2026-10-14 | 0.9 | Recorded D-17 (Q-23) | Claude (PM agent), for review |
| 2026-10-14 | 0.10 | Recorded D-18 to D-25 (Q-5, Q-3, Q-8, Q-12, Q-13, Q-16, Q-17, Q-15) | Claude (PM agent), for review |
| 2026-10-14 | 0.11 | Recorded D-26 to D-28 (Q-9, Q-11, Q-14); all questions resolved | Claude (PM agent), for review |
| 2026-10-14 | 0.12 | Recorded D-29, D-30 (GAP-9, GAP-10); added PROPOSED epic order and PROPOSED Epic 1 goal, stories and acceptance criteria | Claude (PM agent), for review |
| 2026-10-14 | 0.13 | Recorded D-31, D-32 (epic order and Epic 1 approved); added PROPOSED Epic 2 | Claude (PM agent), for review |
| 2026-10-14 | 0.14 | Recorded D-33 (Epic 2 approved); added PROPOSED Epic 6 (RAG, build order 3) | Claude (PM agent), for review |
| 2026-10-14 | 0.15 | Recorded D-34 (Epic 6 approved); added PROPOSED Epic 8 (Real-time Data, build order 4) | Claude (PM agent), for review |
| 2026-10-14 | 0.16 | Recorded D-35 (Epic 8 approved); added PROPOSED Epic 3 (Core Agents, build order 5) | Claude (PM agent), for review |
| 2026-10-14 | 0.17 | Recorded D-36 (Epic 3 approved; Story 2.5 gains asset type); added PROPOSED Epic 5 (Workflow Orchestration, build order 6) | Claude (PM agent), for review |
| 2026-10-14 | 0.18 | Recorded D-37 (Epic 5 approved); added PROPOSED Epic 4 (Advanced Agents, build order 7) | Claude (PM agent), for review |
| 2026-10-14 | 0.19 | Recorded D-38 (Epic 4 approved); added PROPOSED Epic 7 (User Interface, build order 8) | Claude (PM agent), for review |
| 2026-10-14 | 0.20 | Recorded D-39 (Epic 7 approved); added PROPOSED Epics 9 and 10, PROPOSED target users (GAP-7) and PROPOSED performance targets (GAP-8) | Claude (PM agent), for review |
| 2026-10-14 | 0.21 | Recorded D-40; all gaps and questions resolved; added checklist results (§7) and handoff prompts (§8) | Claude (PM agent), for review |
| 2026-10-14 | 1.0 | Recorded D-41 to D-43 (checklist findings applied); PRD marked final | Claude (PM agent), approved by PM |

---

## 2. Requirements

Optionality labels such as `[OPTIONAL]`, `[STRETCH]`, "if time permits" and "stretch goal" are copied exactly as they appear in the source. Where the sources disagree on whether something is required, both statements are kept and the conflict is flagged.

### 2.1 Functional Requirements

**Specialized agents** [PS §2: "The system consists of six specialized agents"; PB: "Six specialist agents collaborate behind a single chat interface"]

- **FR1: Finance Q&A Agent:** Handles general financial education queries. [PS §2] "Explains concepts like compound interest, ETFs vs mutual funds." [PB] Develop Finance Q&A Agent with RAG integration. [MS 3]
- **FR2: Portfolio Analysis Agent:** Reviews and analyzes user portfolios. [PS §2] "Analyzes uploaded holdings for diversification and risk." [PB] Build Portfolio Analysis Agent with calculation capabilities. [MS 3]
- **FR3: Market Analysis Agent:** Provides real-time market insights. [PS §2] "Pulls live quotes and explains what the numbers mean." [PB] Create Market Analysis Agent with API integration. [MS 3]
- **FR4: Goal Planning Agent:** Assists with financial goal setting and planning. [PS §2] "Calculates how much to save monthly to hit a target." [PB] Implement Goal Planning Agent with projection algorithms. [MS 4]
- **FR5: News Synthesizer Agent:** Summarizes and contextualizes financial news. [PS §2] "Summarizes current financial news with sources." [PB] Build News Synthesizer Agent (if time permits). [MS 4] News search via "SerpApi or Tavily". [PB] **Decision D-1:** required. **Decision D-5:** news search may use SerpApi and Tavily. **Decision D-8:** SerpApi results are cached with a mock fallback; Tavily results are not. **Decision D-9:** the two providers are not fallbacks for each other; a failed news request falls back to cache. **Decision D-10:** news search uses SerpApi. **Decision D-11:** Tavily results are also cached (replaces the Tavily part of D-8). **Decision D-14:** Tavily is optional in v1.
- **FR6: Tax Education Agent:** Explains tax concepts and account types. [PS §2] "Explains 401(k) vs IRA vs Roth without giving tax advice." [PB] Develop Tax Education Agent (stretch goal). [MS 4] **Decision D-1:** required. **Decision D-7:** may give advice; advice-type responses must include a disclaimer. **Decision D-21:** US only.
- **FR7: Agent coverage:** "Implement all six specialized agents with distinct capabilities." [PS §3] Working prototype must have "At least above mentioned working agents with specialized capabilities." [PS §5] "Six specialist agents collaborate behind a single chat interface." [PB] "Focus on quality over quantity. Implement at least 4-5 agents well rather than rushing through all six. The core agents (Q&A, Portfolio, Market, Goal) should be prioritized." [FAQ Tech 3] **Decision D-1:** all six agents are required.
- **FR8: Base agent:** Implement base agent class with common functionality. [MS 3]

**Workflow orchestration and conversation**

- **FR9: Workflow routing:** "The workflow router should decide which agent(s) to invoke based on the user query classification." [FAQ Tech 2] "A LangGraph router classifies each query and dispatches it to the right agent." [PB] Data Flow: "User Query → Workflow Router → Appropriate Agent(s) → RAG Retrieval → LLM Processing → Response Generation → User Interface" [PS §2] **Decision D-16:** one agent per query. **Decision D-22:** RAG retrieval is used only when an agent needs it, not on every query.
- **FR10: Agent interfaces:** "Each agent should have clearly defined inputs/outputs." [FAQ Tech 2]
- **FR11: Conversation context:** "The system maintains conversation history and user profiles, enabling progressively sophisticated guidance as users learn." [PS §1] Build conversation state management; add conversation memory and context preservation. [MS 5] Conversational Flow: "Natural interactions with context preservation." [PS §6] Multi-turn conversations with different agents. [PS §5] **Decision D-15:** kept for the current session only; profiles do not persist.
- **FR12: Personalization:** "The multi-agent system adapts to each user's knowledge level, goals, and risk tolerance." [PS §1] "Meets beginners where they are." [PB] **Decision D-15:** within the current session only. (see GAP-5)

**Portfolio analysis**

- **FR13: Portfolio analysis of user input** [PS §5]; "analyzes uploaded holdings for diversification and risk" [PB]. "Essential metrics include: total value, allocation percentages, expense ratios, basic diversification score, and simple risk assessment based on asset types." [FAQ Domain 3] Evaluation: "Meaningful metrics and recommendations." [PS §6] **Decision D-3:** recommendations are allowed and must carry a disclaimer (see FR28). **Decision D-27:** expense ratios come from the uploaded holdings file, with a built-in table of common funds as a backup. **Decision D-29:** holdings are uploaded as CSV with `ticker`, `shares` and optional `expense_ratio`.

**Goal planning**

- **FR14: Goal planning:** "Ability to plan financial goals keeping risk appetite in mind." [PS §5] "Calculates how much to save monthly to hit a target." [PB] Implement Goal Planning Agent with projection algorithms. [MS 4] **Decision D-15:** risk appetite is kept for the current session only.

**Market data**

- **FR15: Live quotes:** "Real-time market data lookup" [PS §5]. "Connect to Alpha Vantage/yFinance API for live quotes." [PS §3] "Integrate Alpha Vantage API." [MS 8] "Alpha Vantage — Live market data." [PB] **Decision D-2:** Alpha Vantage only; yFinance is out. **Decision D-18:** the Markets tab shows 3–5 stocks; mock data is used when the daily limit runs out, and it is labeled (D-24).
- **FR16: Market trends:** "Provide market trend analysis and insights." [PS §3] Market Intelligence: "Relevant real-time insights." [PS §6] "Explains what the numbers mean." [PB]
- **FR17: Data freshness:** "Add data freshness indicators." [MS 8]

**Knowledge base and RAG**

- **FR18: Content corpus:** "Curate 50-100 financial education articles" [PS §3] "covering basics" [MS 2]. "RAG over a 50-100 article knowledge base grounds answers in verified content." [PB] "Focus on common concepts like diversification, compound interest, and major investment types. Use reputable sources like Investopedia for reference." [FAQ Domain 1]
- **FR19: Categories:** "Structure content by categories (stocks, bonds, ETFs, etc.)" [MS 2]; "Create category-based filtering for targeted responses." [PS §3]
- **FR20: Glossary:** "Create glossary of financial terms." [MS 2]
- **FR21: Retrieval:** "Implement vector indexing for efficient retrieval." [PS §3] "Set up FAISS vector database; Implement document chunking and embedding; Build retrieval pipeline with relevance scoring." [MS 6] "FAISS vector store, sentence-transformers (all-MiniLM-L6-v2) for embeddings." [PB]
- **FR22: Source attribution:** "Include source attribution for transparency." [PS §3] "Add source attribution to responses." [MS 6] "Always cite sources." [FAQ Domain 2] News summaries "with sources." [PB]

**User interface**

- **FR23: Conversational interface:** "Application with conversational interface" [PS §3]; "Web interface for conversation" [PS §5]; "Build conversational chat interface." [MS 7] "A single chat interface." [PB]
- **FR24: Portfolio dashboard:** "Portfolio analysis dashboard with visualizations." [PS §3] [MS 7]
- **FR25: Market overview:** "Market overview with real-time data" [PS §3]; "Add market overview visualizations." [MS 7]
- **FR26: Tabs:** "Focus on 3-4 main tabs (Chat, Portfolio, Market, Goals)." [FAQ UI 1] "A Streamlit UI ties it together with tabs for Chat, Portfolio, Markets, Goals, and Knowledge." [PB] Evaluation: "Streamlit Application (10%): Multi-tab interface with responsive design." [PS §6] **Decision D-4:** no Knowledge tab; the tabs are Chat, Portfolio, Markets, Goals.
- **FR27: Visualizations:** "Portfolio pie charts, allocation bar graphs, market trend lines, and goal projection charts." [FAQ UI 2]

**Education vs. advice**

- **FR28: Disclaimers:** "The system must clearly distinguish between education and financial advice, including appropriate disclaimers." [PS §1] "Avoid specific investment advice, and include clear disclaimers that this is for educational purposes only." [FAQ Domain 2] "The system explicitly distinguishes education from advice and adds disclaimers — a real regulatory concern in fintech." [PB] Tax: "without giving tax advice." [PB] **Decision D-3:** a disclaimer must be shown whenever the system provides advice or recommendations. **Decision D-7:** this applies to all agents, including Tax. Advice may be given, and every advice-type response must include a disclaimer. This replaces "avoid specific investment advice" [FAQ Domain 2] and "without giving tax advice" [PB].

**MCP integration**

- **FR29: [OPTIONAL] MCP server for Claude Desktop integration:** "Expose finance tools via Model Context Protocol; Enable seamless integration with Claude Desktop; Document protocol implementation." [PS §3] Labeled "[STRETCH]" in [MS 11]. Evaluation: "MCP Server (5%): Bonus points for Claude Desktop integration." [PS §6] Not mentioned in [PB]. **Decision D-28:** skipped; not built in v1.

### 2.2 Non-Functional Requirements

- **NFR1: Error handling:** "Implement error handling and fallback mechanisms." [PS §3] "Create fallback mechanisms for errors." [MS 5] "Proper error handling and logging throughout." [PS §5]
- **NFR2: Accuracy and reliability:** "Financial information must be accurate and up-to-date, with robust error handling for API failures." [PS §1] "Stick to widely accepted principles." [FAQ Domain 2] "Grounds answers in verified content." [PB]
- **NFR3: Market-data caching:** "Implement caching strategy for performance." [PS §3] "Implement caching for market data (30-minute TTL recommended)." [FAQ Tech 4] "Students must build aggressive caching (30-min TTL) and mock data fallbacks early — this is the #1 demo killer." [PB] **Decision D-18:** keep live usage within the free quota (3–5 stocks on the Markets tab). **Decision D-41:** daily price history is cached for 24 hours.
- **NFR4: API rate limits and failures:** "Handle rate limits and API failures gracefully." [PS §3] "Use exponential backoff for retries, and provide fallback mechanisms with cached or mock data when APIs are unavailable." [FAQ Tech 4] External API quotas [PB]: Alpha Vantage "Free: 25 req/day, 5 req/min"; SerpApi "100/mo"; Tavily "1,000/mo". "Alpha Vantage's 25-req/day cap is tight." [PB] **Decision D-24:** cached and mock data are clearly labeled for users.
- **NFR5: LLM rate limiting:** "Ensure you implement proper rate limiting." [FAQ Tech 1]
- **NFR6: Test coverage:** "Build comprehensive test suite with 80%+ coverage." [PS §3] "Aim for 80%+ coverage. Test individual agents, workflow routing, RAG retrieval, error handling, and integration points. Include edge cases like malformed queries." [FAQ T&D 1] Also labeled "[Optional] Comprehensive test suite with unit and integration tests" [PS §5] and "[Optional] Testing & Quality Assurance" [MS 9]. **Decision D-13:** required.
- **NFR7: User trust:** "Transparency, citations, and conservative recommendations." [PS §1]
- **NFR8: Plain language:** "Clear, jargon-free explanations." [PS §1] "Balance technical sophistication with accessibility." [PS §4]
- **NFR9: Usability:** "Keep it clean and intuitive... Ensure responsive design and clear navigation for beginners." [FAQ UI 1] "Keep visualizations simple and clearly labeled." [FAQ UI 2]
- **NFR10: Scalability:** "The AI system can serve thousands of users simultaneously." [PS §1] "Consider scalability, user trust, and regulatory compliance throughout your implementation." [PS §4] **Decision D-20:** local deployment; serving thousands of users at once is not a v1 requirement.
- **NFR11: Sessions and authentication:** "You don't need complex authentication - simple session-based identification is sufficient." [FAQ UI 3]
- **NFR12: Deployment:** "Local deployment is sufficient, but containerization (Docker) and cloud deployment readiness earn bonus points. Focus on making the system easily runnable by evaluators." [FAQ Sub 4] "Without too much infrastructure overhead." [PB]
- **NFR13: Performance:** Performance benchmarks are a required deployment artifact [PS §5]; "Performance optimization" [MS 9]; technical design doc covers "Performance considerations" [PS §5]. No performance targets are given in the sources.
  **Targets (fills GAP-8; approved, D-40).** Measured locally (D-20) with `gpt-4o-mini` (D-6), one user at a time:
  - App startup, including loading the FAISS index: 10 seconds or less.
  - Chat answer, from sending a question to the full answer appearing: median 6 seconds or less, 90th percentile 12 seconds or less.
  - Knowledge-base retrieval: 300 ms or less per query.
  - Market data: 1 second or less from cache; 3 seconds or less for a live call.
  - Portfolio metrics for up to 50 holdings, with prices cached: 2 seconds or less.
  - Holdings upload limit: 200 rows or 1 MB.
- **NFR14: Async:** "Async Python throughout." [PB] **Decision D-17:** adopted; the Streamlit integration approach is left to the architecture document.

### 2.3 Submission Deliverables

*The source lists these as submission requirements. They are kept here as a group rather than split into FRs/NFRs (see INTERP-5).* [PS §5]

**Working Prototype**
- Fully functional AI Finance Assistant with all core features:
  - At least above mentioned working agents with specialized capabilities
  - Web interface for conversation
  - Portfolio analysis of user input
  - Real-time market data lookup
  - Ability to plan financial goals keeping risk appetite in mind
- A demo video (5-10 minutes) showcasing:
  - Multi-turn conversations with different agents
  - Portfolio analysis demonstration
  - Market data integration
  - Goal planning example
  - FAQ adds: "Show how agents work together." [FAQ Sub 3]

**Sample Code and Architecture**: well-organized codebase following the prescribed structure (see §4.1)
- [Optional] Comprehensive test suite with unit and integration tests
- [Optional] Configuration management via YAML/environment variables. **Decision D-25:** required.
- Proper error handling and logging throughout

**Documentation**
- Detailed README with: Architecture overview; Setup instructions; API documentation; Usage examples; Troubleshooting guide
- Technical design document covering: System architecture decisions; Agent communication protocols; RAG implementation details; Performance considerations
- FAQ: "Very detailed. Include architecture diagrams, setup instructions, API documentation, usage examples, and troubleshooting guides. Think of it as documentation for a production system." [FAQ T&D 2]
- "Can I use different technologies? Yes, but document your choices... explain your reasoning." [FAQ Sub 2]

**Deployment Artifacts**
- Docker configuration (optional)
- Environment setup files
- Sample data for testing
- Performance benchmarks

---

## 3. User Interface Design Goals

### 3.1 Overall UX Vision
"Keep it clean and intuitive... Ensure responsive design and clear navigation for beginners." [FAQ UI 1] "A multi-agent conversational tutor that meets beginners where they are." [PB] Grading guidance: "Focus on demonstrating sophisticated AI system design rather than UI polish." [FAQ Sub 1]

### 3.2 Key Interaction Paradigms
- Conversational chat with multi-turn conversations across different agents. [PS §3, §5] Specialist agents "collaborate behind a single chat interface." [PB]
- "Conversational Flow (8%): Natural interactions with context preservation." [PS §6]

### 3.3 Core Screens and Views
The sources disagree on the tab set:
- [FAQ UI 1]: "3-4 main tabs (Chat, Portfolio, Market, Goals)"
- [PB]: "tabs for Chat, Portfolio, Markets, Goals, and Knowledge"

**Decision D-4:** no Knowledge tab. The tabs are Chat, Portfolio, Markets, Goals.

Screen content from the sources:
- **Chat**: conversational interface [PS §3]
- **Portfolio**: portfolio analysis dashboard with visualizations [PS §3]; uploaded holdings [PB]
- **Markets**: market overview with real-time data [PS §3]
- **Goals**: goal planning; no screen detail in the source → GAP-6

Visualizations: "Portfolio pie charts, allocation bar graphs, market trend lines, and goal projection charts." [FAQ UI 2]

### 3.4 Accessibility
Not specified. (Voice interface "for accessibility" appears only in Future Directions [PS §7].) → GAP-6

### 3.5 Branding
Product name "Finnie" [PB]. No other branding is specified. → GAP-6

### 3.6 Target Device and Platforms
Web interface [PS §2, §5] with "responsive design" [FAQ UI 1]; Streamlit UI [PB]. Native mobile apps are listed under Future Directions [PS §7].

---

## 4. Technical Assumptions

### 4.1 Repository Structure
"Well-organized codebase following the prescribed structure:" [PS §5]

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

Repository type (monorepo/polyrepo): not stated. The prescribed structure suggests a single repository, but this has not been confirmed. → GAP-10 **Decision D-30:** single repository.

### 4.2 Service Architecture
"The AI Finance Assistant employs a sophisticated multi-agent architecture built on modern AI frameworks." [PS §2] Monolith vs. services is not stated. Microservices are listed only under Future Directions ("Distributed Architecture") [PS §7]. → GAP-10 **Decision D-30:** single application.

**Core Components** [PS §2]: the original table, which lists alternatives for each component

| Component | Technology | Purpose |
|---|---|---|
| Multi-Agent System | LangChain/LangGraph/CrewAI | Orchestrates specialized agents for different financial domains |
| Language Model | Google Gemini/Open AI GPT/Claude Sonnet | Powers natural language understanding and generation |
| Vector Database | FAISS/Chroma DB/Pinecone DB | Enables semantic search over financial knowledge base |
| Market Data | Alpha Vantage API/yFinance API | Provides real-time stock quotes and financial data |
| Web Interface | Streamlit/Gradio/React | Delivers interactive user experience |
| State Management | LangGraph/CrewAI | Maintains conversation context and user sessions |

**Tech Stack** [PB]: "LangGraph, LangChain, OpenAI (or Google Gemini as a free alternative), FAISS vector store, sentence-transformers (all-MiniLM-L6-v2) for embeddings, Streamlit UI, async Python throughout."

**Decision D-2:** the [PB] tech stack is the decision. Alternatives in the [PS §2] table that are not in [PB] (CrewAI, Chroma DB, Pinecone DB, yFinance, Gradio, React) are out.

**Decision D-6:** the LLM is OpenAI `gpt-4o-mini`, configured as `OPENAI_MODEL=gpt-4o-mini`.

**External APIs & Services Required** [PB]

| Service | Purpose | Notes |
|---|---|---|
| OpenAI API | LLM for all agents | Provided by the program |
| Alpha Vantage | Live market data | Free: 25 req/day, 5 req/min — students sign up themselves |
| SerpApi or Tavily | News search | Free: SerpApi 100/mo, Tavily 1,000/mo — students sign up themselves |

**Decision D-5:** news search may use both SerpApi and Tavily. The PM will provide API keys for both. **Decision D-8:** because of SerpApi's 100 requests/month limit [PB], SerpApi results are cached with a mock fallback; Tavily results are not. **Decision D-9:** SerpApi and Tavily are not fallbacks for each other; a failed news request falls back to cache. **Decision D-10:** news search uses SerpApi. **Decision D-11:** Tavily results are also cached (replaces the Tavily part of D-8). **Decision D-14:** Tavily is optional in v1.

### 4.3 Testing Requirements
See NFR6. Milestone 9 [Optional]: "Write comprehensive unit tests; Implement integration tests; Conduct user acceptance testing; Performance optimization." [MS 9] **Decision D-13:** required.

### 4.4 Additional Technical Assumptions and Requests
- **LLM:** "Google Gemini 2.0 Flash is recommended for its balance of performance and cost. The free tier (60 requests/minute) is sufficient for development. Ensure you implement proper rate limiting." [FAQ Tech 1] "OpenAI (or Google Gemini as a free alternative)"; OpenAI API "Provided by the program." [PB] **Decision D-6:** OpenAI `gpt-4o-mini` (`OPENAI_MODEL=gpt-4o-mini`).
- **Orchestration:** "Use LangGraph's StateGraph for orchestration." [FAQ Tech 2] "Create robust workflow orchestration using LangGraph/CrewAI." [PS §3] "Implement LangGraph workflow for agent routing." [MS 5] "A LangGraph router." [PB] (see Q-4)
- **Embeddings:** "sentence-transformers (all-MiniLM-L6-v2) for embeddings." [PB]
- **Sessions:** "Use Streamlit's session state for conversation memory." [FAQ UI 3]
- **Async:** "Async Python throughout." [PB] **Decision D-17:** adopted.
- **Alternatives allowed:** "Yes, but document your choices. For example, you could use ChromaDB instead of FAISS, or FastAPI instead of Streamlit, but explain your reasoning." [FAQ Sub 2]
- **Configuration:** "[Optional] Configuration management via YAML/environment variables." [PS §5] **Decision D-25:** required; configuration via `config.yaml` and environment variables (including API keys and `OPENAI_MODEL`).
- **Containerization:** "Docker configuration (optional)" [PS §5]; earns bonus points [FAQ Sub 4].
- **Reference implementation:** "A complete reference implementation is provided." [PB] **Decision D-12:** ignored; not used or consulted.

---

## 5. Epic List

*Mapped one-to-one from the 11 Core Milestones in the FAQ document, in the source order, with the source titles and labels. See INTERP-1 and GAP-3, GAP-4.*

| Epic | Title (source wording) | Source label | **v1 build order** (D-31) | Epic goal |
|---|---|---|---|---|
| 1 | Initial Research & Architecture Design | | 1 | Approved (D-32), see Epic 1 |
| 2 | Knowledge Base Development | | 2 | Approved (D-33), see Epic 2 |
| 3 | Core Agent Implementation | | 5 | Approved (D-36), see Epic 3 |
| 4 | Advanced Agent Development | | 7 | Approved (D-38), see Epic 4 |
| 5 | Workflow Orchestration | | 6 | Approved (D-37), see Epic 5 |
| 6 | RAG System Implementation | | 3 | Approved (D-34), see Epic 6 |
| 7 | User Interface Development | | 8 | Approved (D-39), see Epic 7 |
| 8 | Real-time Data Integration | | 4 | Approved (D-35), see Epic 8 |
| 9 | Testing & Quality Assurance | [Optional] — required (D-13) | 9 | Approved (D-40), see Epic 9 |
| 10 | Documentation & Deployment | | 10 | Approved (D-40), see Epic 10 |
| 11 | MCP Server Implementation | [STRETCH] — **out of v1 (D-28)** | — | n/a |

**Order rationale (approved, D-31):**
- Epic 1 ends with a runnable app skeleton (Story 1.7), so every later epic adds to a working local app.
- Knowledge Base (2) and RAG (6) come before Core Agents (3) because the Finance Q&A Agent is built "with RAG integration" [MS 3].
- Real-time Data Integration (8), including caching and mock fallbacks, moves before Core Agents because the Market Analysis Agent needs it, and [PB] says to build "mock data fallbacks early — this is the #1 demo killer."
- Workflow Orchestration (5) follows Core Agents so the router has agents to dispatch to; Advanced Agents (4) then plug into the working router.
- User Interface (7) fills in the tabs once agents and data exist. Testing (9) still runs throughout: every story's acceptance criteria include its own tests, and Epic 9 covers integration, user acceptance and performance.

---

## 6. Epic Details

Epics appear in their milestone (source) order; the build order is shown under each epic heading and in §5 (D-31). Story titles 1.1–11.3 are milestone bullets copied word for word. The source had no story statements, acceptance criteria or epic goals (GAP-1 to GAP-3). Those, and the new stories marked "(new)", were drafted from the source and the PM's decisions and approved epic by epic (D-32 to D-40). Epic 11 is out of scope for v1 (D-28) and was not filled in.

### Epic 1: Initial Research & Architecture Design [MS 1]

> **Approved by the PM (D-32).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2, GAP-3 and GAP-5. Story titles 1.1–1.4 are source wording. Stories 1.5–1.7 are new stories that give a home to requirements no milestone covered (GAP-5).

**Epic goal:** Establish Finnie's foundation: a researched and documented architecture, a working development environment in the prescribed project structure, configuration and logging, and a runnable local app skeleton that every later epic builds on.

#### Story 1.1: Study existing financial education platforms and robo-advisors [MS 1]
**Story:** As the Finnie developer, I want to review existing financial education platforms and robo-advisors, so that Finnie's design addresses what they leave out for beginners.

**Acceptance criteria:**
1. A research note in `docs/` summarizes at least three financial education platforms or robo-advisors.
2. For each one, the note records what it offers beginners and where it falls short (for example, jargon, product-pushing without teaching [PB]).
3. The note lists the implications for Finnie's design.

#### Story 1.2: Research LangChain/LangGraph/CrewAI multi-agent architectures [MS 1]
**Story:** As the Finnie developer, I want to research multi-agent patterns in LangGraph and LangChain, so that the architecture uses them correctly.

**Acceptance criteria:**
1. A research note in `docs/` covers LangGraph `StateGraph` routing [FAQ Tech 2], state management, and async execution (D-17).
2. The note records why LangGraph/LangChain were chosen and CrewAI was not (D-2).

#### Story 1.3: Design system architecture and agent communication protocols [MS 1]
**Story:** As the Finnie developer, I want a documented architecture and agent communication design, so that every agent and component is built against the same contracts.

**Acceptance criteria:**
1. A technical design document in `docs/` includes an architecture diagram [FAQ T&D 2].
2. It defines the router's query classification and single-agent dispatch (FR9, D-16).
3. It defines each of the six agents' inputs and outputs (FR10, D-1).
4. It defines the session-only conversation state schema (FR11, D-15).
5. It describes when agents use RAG retrieval (D-22).
6. It describes caching, rate-limit handling, cache/mock fallbacks and data labels for Alpha Vantage and news search (NFR3, NFR4, D-8 to D-11, D-18, D-24).
7. It describes how async code is called from Streamlit (D-17).
8. It describes how advice-type responses get a disclaimer (FR28, D-7).

#### Story 1.4: Set up development environment and project structure [MS 1]
**Story:** As the Finnie developer, I want a reproducible development environment in the prescribed project structure, so that the project is easy to run for me and for evaluators.

**Acceptance criteria:**
1. The repository follows the prescribed structure (§4.1) as a single repository with a single application (D-30).
2. `requirements.txt` lists all dependencies with pinned versions.
3. The README includes setup instructions that work from a fresh clone.
4. `pytest` runs and reports coverage (D-13).

#### Story 1.5 (new): Configuration management [D-25]
**Story:** As the Finnie developer, I want all settings and API keys in configuration, so that nothing is hard-coded and the app is easy to set up.

**Acceptance criteria:**
1. Settings load from `config.yaml` and environment variables. Environment variables override `config.yaml`.
2. Supported keys include `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`, D-6), `ALPHA_VANTAGE_API_KEY`, `SERPAPI_API_KEY`, `TAVILY_API_KEY` (optional, D-14) and the market-data cache TTL (default 30 minutes, NFR3).
3. If a required key is missing, the app stops at startup with a clear message naming the missing key.
4. A `.env.example` is committed; `.env` is excluded from version control.
5. API keys never appear in logs or in the UI.

#### Story 1.6 (new): Logging [NFR1]
**Story:** As the Finnie developer, I want consistent logging throughout the app, so that I can trace and fix problems.

**Acceptance criteria:**
1. All modules use one shared logging setup, with the log level set in configuration.
2. Logs record which agent handled each query, external API calls, cache hits and misses, fallbacks, and errors.
3. Secrets are never logged (Story 1.5, AC 5).

#### Story 1.7 (new): Runnable app skeleton
**Story:** As a beginner investor, I want to open Finnie locally and see its main sections, so that the app is usable from the first epic onward.

**Acceptance criteria:**
1. `streamlit run` starts the app locally with valid configuration (D-20).
2. The app shows four tabs: Chat, Portfolio, Markets, Goals (D-4), each with placeholder content.
3. An automated smoke test confirms the app starts without errors.

### Epic 2: Knowledge Base Development [MS 2]

> **Approved by the PM (D-33).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2, GAP-3 and GAP-5. Story titles 2.1–2.4 are source wording. Story 2.5 is a new story for D-27.

**Epic goal:** Build the curated, categorized, US-focused financial education content and test data that the RAG system and agents rely on: 50-100 articles, a glossary, sample portfolios, and a built-in expense-ratio table.

#### Story 2.1: Curate 50-100 financial education articles covering basics [MS 2]
**Story:** As a beginner investor, I want Finnie's answers to come from a curated library of plain-language articles, so that I can trust what I learn.

**Acceptance criteria:**
1. Between 50 and 100 articles are stored under `src/data/` in a consistent text format (FR18).
2. Together they cover the common concepts named in the sources: diversification, compound interest and major investment types [FAQ Domain 1], ETFs vs. mutual funds [PB], and US retirement account types 401(k), IRA and Roth [PB].
3. Content is US-focused (D-21) and written in plain, jargon-free language (NFR8).
4. Each article records its title, category, source name and source URL, so answers can cite it (FR22). Sources are reputable, such as Investopedia, the Bogleheads wiki and SEC investor.gov [FAQ Resources].
5. Articles are written or summarized in the project's own words with links to their sources, not copied verbatim from those sites.

#### Story 2.2: Structure content by categories (stocks, bonds, ETFs, etc.) [MS 2]
**Story:** As the Finnie developer, I want every article assigned to a category, so that retrieval can be filtered for targeted responses (FR19).

**Acceptance criteria:**
1. A fixed category list is defined in one place. Starting list: Investing Basics, Stocks, Bonds, ETFs & Mutual Funds, Retirement & Tax Accounts, Portfolio & Risk, Markets, Goals & Saving.
2. Every article has exactly one category from the list.
3. A validation test fails if an article has a missing or unknown category, or if the article count is outside 50-100.

#### Story 2.3: Create glossary of financial terms [MS 2]
**Story:** As a beginner investor, I want plain-language definitions of financial terms, so that jargon doesn't block me.

**Acceptance criteria:**
1. A glossary of at least 50 terms is stored under `src/data/` (FR20).
2. Each entry has a term, a one-to-three-sentence plain-language definition, a category from Story 2.2, and, where one exists, a link to a related article.
3. The glossary is in a format the RAG system can index alongside the articles (Epic 6).

#### Story 2.4: Prepare sample portfolio data for testing [MS 2]
**Story:** As the Finnie developer, I want sample holdings files, so that portfolio analysis can be tested and demonstrated.

**Acceptance criteria:**
1. At least three valid sample CSV files use the D-29 format (`ticker`, `shares`, optional `expense_ratio`) with US tickers (D-21): a diversified portfolio, a portfolio concentrated in one or two stocks, and one with some `expense_ratio` values missing.
2. At least one malformed sample file exists for error-handling tests (for example, a missing column or a non-numeric share count) [FAQ T&D 1].
3. The samples are listed in the README as sample data for testing [PS §5].

#### Story 2.5 (new): Built-in expense-ratio table [D-27]
**Story:** As a beginner investor, I want Finnie to know the fees of common funds, so that my portfolio analysis includes expense ratios even when my file doesn't list them.

**Acceptance criteria:**
1. A table under `src/data/` lists common US funds and ETFs with their expense ratio, asset type (added with D-36, used by Story 3.3), an "as of" date and a source.
2. When an uploaded holding has no `expense_ratio`, the table value is used. A value in the uploaded file always takes priority.
3. Individual stocks are recognized as having no expense ratio, and a fund missing from both the file and the table is reported as "unknown", not zero.

### Epic 3: Core Agent Implementation [MS 3]
*Build order: 5th (D-31).*

> **Approved by the PM (D-36).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2, GAP-3 and GAP-5. Story titles 3.1–3.4 are source wording. Requirements no milestone covered are placed here: advice disclaimers (FR28, D-7) and LLM rate limiting (NFR5) in Story 3.1, and market trend analysis (FR16) in Story 3.4.

**Epic goal:** Deliver the shared agent foundation and the three core agents (Finance Q&A, Portfolio Analysis, Market Analysis), each producing accurate, plain-language answers with sources, freshness labels and disclaimers where they apply.

#### Story 3.1: Implement base agent class with common functionality [MS 3]
**Story:** As the Finnie developer, I want every agent built on one shared base, so that all six agents behave consistently (FR8, FR10).

**Acceptance criteria:**
1. The base agent defines one async interface (D-17): it takes the user's message and the session state and returns a response with the answer text, any sources (Story 6.4), any data freshness labels (Story 8.4), and whether the response is advice or education.
2. Agents call OpenAI through one shared client that uses `OPENAI_MODEL` (D-6).
3. LLM calls are rate-limited and retried with backoff, with limits set in configuration (NFR5).
4. Every response marked as advice gets a disclaimer added automatically, using disclaimer text set in configuration (FR28, D-7). Education-only responses get none. When it is uncertain whether a response is advice, it is treated as advice (D-43).
5. If an agent fails, the user gets a friendly message instead of an error, and the failure is logged (NFR1, Story 1.6).
6. Each agent's system prompt targets beginners and plain, jargon-free language (NFR8).
7. Tests use a mocked LLM and cover the advice/education flag (including borderline advice-detection cases, D-43), disclaimer insertion and failure handling.

#### Story 3.2: Develop Finance Q&A Agent with RAG integration [MS 3]
**Story:** As a beginner investor, I want to ask general finance questions and get clear, sourced answers, so that I can learn concepts like compound interest or ETFs vs. mutual funds (FR1).

**Acceptance criteria:**
1. The agent answers general financial education questions, using knowledge-base retrieval (Epic 6) when needed (D-22).
2. Answers built on retrieved content list their sources (Story 6.4).
3. When the knowledge base has nothing relevant, the agent says so instead of guessing (Story 6.3, AC 3).
4. A test set of at least 10 beginner questions, including compound interest and ETFs vs. mutual funds [PB], runs against a mocked LLM and checks that each answer is grounded in the expected article.

#### Story 3.3: Build Portfolio Analysis Agent with calculation capabilities [MS 3]
**Story:** As a beginner investor, I want to upload my holdings and see how diversified and risky they are, so that I understand my portfolio (FR2, FR13).

**Acceptance criteria:**
1. The agent accepts a holdings CSV in the D-29 format. A malformed file gets a clear message that lists each problem (for example, "row 3: shares is not a number"); nothing crashes.
2. It calculates the essential metrics [FAQ Domain 3]: total value (shares × current price from Epic 8), allocation percentages, weighted average expense ratio (D-27), a basic diversification score and a simple risk assessment based on asset types.
3. All metrics are calculated in code, not by the LLM. The LLM only explains the results in plain language.
4. The diversification score and risk assessment formulas are documented in the technical design document (Story 1.3).
5. Asset types come from the built-in fund table (Story 2.5, extended with an asset-type column). Tickers not in the table are treated as individual stocks.
6. Prices show their freshness label (Story 8.4). A holding with no live, cached or mock price is shown as "price unavailable" and left out of the totals, with a note saying so (D-41).
7. Recommendations are allowed and carry a disclaimer (D-3, D-7).
8. Unit tests check every metric against the sample portfolios (Story 2.4), including missing expense ratios and the malformed file.

#### Story 3.4: Create Market Analysis Agent with API integration [MS 3]
**Story:** As a beginner investor, I want to ask about a stock or fund and get its current price and recent trend explained, so that I understand what the numbers mean (FR3, FR16).

**Acceptance criteria:**
1. The agent looks up current quotes and price history through the Epic 8 client, so caching, limits and fallbacks apply.
2. It reports price change over 1 week, 1 month and 3 months, calculated in code from the price history (FR16).
3. It explains in plain language what the numbers mean (for example, what a 2% daily drop means for a beginner) [PB].
4. Every figure shows its freshness label (Story 8.4).
5. Advice-type responses carry a disclaimer (D-7).
6. An unknown ticker gets a friendly "not found" message (Story 8.1, AC 4).
7. Tests use mocked market data and a mocked LLM.

### Epic 4: Advanced Agent Development [MS 4]
*Build order: 7th (D-31).*
**Decision D-1:** Stories 4.2 and 4.3 are required. Their "(if time permits)" and "(stretch goal)" labels are kept as source wording only.

> **Approved by the PM (D-38).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2 and GAP-3. Story titles 4.1–4.4 are source wording.

**Epic goal:** Complete the six-agent system (D-1) with the Goal Planning, News Synthesizer and Tax Education agents, plugged into the working router, and prove that all six work together in one conversation.

#### Story 4.1: Implement Goal Planning Agent with projection algorithms [MS 4]
**Story:** As a beginner investor, I want to know how much to save each month to reach a goal, so that I have a realistic plan that fits my risk tolerance (FR4, FR14).

**Acceptance criteria:**
1. The agent gathers the target amount, the target date (or number of years) and current savings. If any are missing, it asks for them in the chat.
2. It uses the session risk tolerance (Story 5.5), asking for it if not set.
3. Each risk level maps to an assumed annual return. These rates are set in configuration and documented, with their source, in the technical design document.
4. The required monthly saving and a year-by-year projection are calculated in code, not by the LLM. The projection feeds the goal projection chart (FR27).
5. The answer states the assumed return and that results are estimates. Advice-type answers carry a disclaimer (D-7).
6. Impossible inputs (a target date in the past, negative amounts, current savings already above the target) get a clear explanation, not an error.
7. Unit tests check the calculations against known values.

#### Story 4.2: Build News Synthesizer Agent (if time permits) [MS 4]
**Story:** As a beginner investor, I want current financial news summarized and explained, so that I understand why it matters to me (FR5).

**Acceptance criteria:**
1. The agent gets news through the Epic 8 news client (Story 8.5), so caching and fallbacks apply.
2. It summarizes the news in plain language and explains why it matters to a beginner [PS §2: "contextualizes"].
3. Every news item in the answer cites its source and link [PB: "with sources"].
4. Results show their freshness label (Story 8.4); mock news is labeled "Sample data".
5. If no relevant news is found, the agent says so.
6. Tests use mocked news and a mocked LLM.

#### Story 4.3: Develop Tax Education Agent (stretch goal) [MS 4]
**Story:** As a beginner investor, I want US tax concepts and account types explained, so that I understand options like 401(k), IRA and Roth (FR6).

**Acceptance criteria:**
1. The agent covers US tax concepts and account types only (D-21), including 401(k), IRA and Roth [PB].
2. It retrieves from the knowledge base filtered to the Retirement & Tax Accounts category (Story 6.5) and cites its sources.
3. Figures that change by year (for example, contribution limits) come from the knowledge base with their "as of" year, never from the LLM's own memory.
4. Advice-type answers carry a disclaimer (D-7).
5. Tests use a mocked LLM and a tax question set.

#### Story 4.4: Test inter-agent communication [MS 4]
**Story:** As the Finnie developer, I want proof that all six agents work together in one conversation, so that the system works as a whole (FR7, D-1).

**Acceptance criteria:**
1. The "coming soon" replies from Story 5.1 are removed; all six agents are reachable through the router.
2. An automated multi-turn test conversation reaches all six agents in one session (D-16), with each agent using the shared session state (Story 5.2).
3. A follow-up that relies on an earlier turn handled by a different agent is answered correctly (for example, a tax question about an account type mentioned during goal planning).
4. The routing test set (Story 5.1, AC 6) is extended to all six agents and still meets the 90% target.

### Epic 5: Workflow Orchestration [MS 5]
*Build order: 6th (D-31).*

> **Approved by the PM (D-37).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2, GAP-3 and GAP-5. Story titles 5.1–5.4 are source wording. Story 5.5 is a new story for session personalization (FR12, D-15), which no milestone covered.

**Epic goal:** Connect the chat to the agents through a LangGraph workflow that routes each question to the right agent, keeps the conversation's context for the session, adapts to the user's level and risk tolerance, and never breaks on bad input or failures. This epic carries the most grading weight (D-19).

#### Story 5.1: Implement LangGraph workflow for agent routing [MS 5]
**Story:** As a beginner investor, I want to ask anything in one chat and have the right specialist answer, so that I don't have to know which agent to use (FR9).

**Acceptance criteria:**
1. The workflow is a LangGraph `StateGraph` [FAQ Tech 2] that runs asynchronously (D-17).
2. The router classifies each query and sends it to exactly one of the six agents (D-1, D-16).
3. Ambiguous questions get a short clarifying question. Questions unrelated to personal finance get a polite note about what Finnie can help with.
4. Until the Goal, News and Tax agents exist (Epic 4), queries routed to them get a "coming soon" reply.
5. The Chat tab is connected to the workflow, so a question typed in the app gets an agent's answer.
6. A routing test set of at least 30 labeled questions (at least 5 per agent) is checked automatically, and at least 90% are routed correctly.
7. The agent that handled each query is logged (Story 1.6).

#### Story 5.2: Build conversation state management [MS 5]
**Story:** As the Finnie developer, I want one defined conversation state, so that the router and every agent share the same context (FR11).

**Acceptance criteria:**
1. A single state schema holds the message history, the agent that handled the last turn, and the session profile (Story 5.5).
2. State lives only for the current session, in Streamlit session state [FAQ UI 3] and the LangGraph state. Nothing persists after the session ends (D-15).
3. A "New conversation" action clears the state.
4. Tests confirm state is kept between turns and cleared on reset.

#### Story 5.3: Create fallback mechanisms for errors [MS 5]
**Story:** As a beginner investor, I want the chat to keep working when something goes wrong, so that I can always continue (NFR1).

**Acceptance criteria:**
1. If the router fails, the query goes to the Finance Q&A Agent.
2. If an agent fails, the user gets a friendly message (Story 3.1, AC 5) and can keep chatting.
3. If OpenAI is unavailable, the app stays up and tells the user the assistant is temporarily unavailable.
4. Empty, very long (over a configured length) and nonsense inputs are handled without errors [FAQ T&D 1].
5. Tests cover each case.

#### Story 5.4: Add conversation memory and context preservation [MS 5]
**Story:** As a beginner investor, I want Finnie to remember what we just talked about, so that I can ask natural follow-ups like "what about bonds?" (FR11).

**Acceptance criteria:**
1. The router and agents receive the recent conversation, up to a configured number of turns.
2. Follow-up questions are routed and answered using that context, including when the follow-up moves to a different agent.
3. A multi-turn test conversation that moves across at least three agents passes. This is how the demo shows agents working together (D-16).

#### Story 5.5 (new): Session personalization [FR12, D-15]
**Story:** As a beginner investor, I want Finnie to adapt to my knowledge level, goals and risk tolerance, so that its guidance fits me.

**Acceptance criteria:**
1. A sidebar lets the user set knowledge level (Beginner, Intermediate), risk tolerance (Conservative, Moderate, Aggressive) and an optional goal note. Knowledge level defaults to Beginner. Risk tolerance has no default.
2. If an agent needs risk tolerance and it isn't set, the agent asks for it in the chat and stores the answer in the session profile.
3. Agents adjust explanation depth to the knowledge level. Goal Planning and Portfolio Analysis use risk tolerance.
4. The profile lasts only for the session (D-15).
5. Tests confirm the profile reaches the agents and that a missing risk tolerance triggers the question.

### Epic 6: RAG System Implementation [MS 6]
*Build order: 3rd (D-31).*

> **Approved by the PM (D-34).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2, GAP-3 and GAP-5. Story titles 6.1–6.4 are source wording. Story 6.5 is a new story for FR19 category-based filtering (GAP-5).

**Epic goal:** Make the knowledge base searchable so agents can ground answers in verified content and cite their sources, using FAISS and all-MiniLM-L6-v2 embeddings (D-2), with retrieval used only when an agent needs it (D-22).

#### Story 6.1: Set up FAISS vector database [MS 6]
**Story:** As the Finnie developer, I want the knowledge base stored in a FAISS index, so that agents can search it quickly.

**Acceptance criteria:**
1. A FAISS index is built from all articles and glossary entries (Epic 2), using sentence-transformers `all-MiniLM-L6-v2` embeddings (D-2).
2. The index is saved to disk and loaded at app startup without re-embedding.
3. A single command rebuilds the index when content changes.
4. If the index is missing or unreadable at startup, the app logs the error and shows a clear message instead of crashing (NFR1).

#### Story 6.2: Implement document chunking and embedding [MS 6]
**Story:** As the Finnie developer, I want articles split into well-formed chunks with metadata, so that retrieval returns focused, citable passages.

**Acceptance criteria:**
1. Articles are split into chunks with chunk size and overlap set in configuration (D-25).
2. Each glossary entry is stored as its own chunk.
3. Every chunk carries its source article's title, category, source name and source URL.
4. Tests confirm there are no empty chunks and that every chunk has complete metadata.

#### Story 6.3: Build retrieval pipeline with relevance scoring [MS 6]
**Story:** As an agent, I want to retrieve the most relevant passages with a relevance score, so that I only ground answers in content that actually matches the question.

**Acceptance criteria:**
1. Retrieval is an async function (D-17) that agents call only when they need it (D-22); it is not run on every query.
2. It returns the top-k chunks with similarity scores, with k set in configuration.
3. Chunks below a configured relevance threshold are dropped. If nothing passes, the agent says it has no verified content on that topic instead of guessing (NFR2).
4. A retrieval test set of at least 20 questions, each mapped to its expected article, is checked automatically. The expected article appears in the top-k results for at least 80% of the questions.

#### Story 6.4: Add source attribution to responses [MS 6]
**Story:** As a beginner investor, I want to see where an answer came from, so that I can trust it and read more (FR22, NFR7).

**Acceptance criteria:**
1. Every response that used retrieved content lists its sources by article title and source link.
2. Each source appears only once, and only sources actually retrieved for that response are listed.
3. Responses that used no retrieved content show no source list.
4. Tests cover all three cases.

#### Story 6.5 (new): Category-based filtering [FR19]
**Story:** As an agent, I want to limit retrieval to certain categories, so that my answers stay on topic (for example, the Tax Education Agent searching only Retirement & Tax Accounts).

**Acceptance criteria:**
1. Retrieval accepts an optional list of categories from the Story 2.2 category list.
2. With a filter, only chunks from those categories are returned. Without one, all categories are searched.
3. An unknown category name raises a clear error.
4. Tests cover filtered, unfiltered and unknown-category retrieval.

### Epic 7: User Interface Development [MS 7]
*Build order: 8th (D-31).*

> **Approved by the PM (D-39).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2, GAP-3 and GAP-6. Story titles 7.1–7.3 are source wording. Story 7.4 is a new story for the Goals tab (D-4, GAP-6). Story 7.5 is a new story for accessibility, branding and responsive design (GAP-6, NFR9).

**Epic goal:** Finish the four tabs (Chat, Portfolio, Markets, Goals, D-4) into a clean, beginner-friendly Streamlit app with simple, clearly labeled charts (FR23–FR27, NFR9).

#### Story 7.1: Build conversational chat interface [MS 7]
**Story:** As a beginner investor, I want a clear chat where I can see who answered and where the answer came from, so that I can learn and trust what I read (FR23).

**Acceptance criteria:**
1. The Chat tab shows the full session conversation and an input box (builds on Story 5.1, AC 5).
2. Each answer shows which agent answered it.
3. Sources (Story 6.4) and freshness labels (Story 8.4) appear under the answer they belong to.
4. Disclaimers (D-7) are visually distinct from the answer text.
5. A loading indicator shows while an answer is being prepared.
6. The "New conversation" action (Story 5.2) is available in the tab.

#### Story 7.2: Implement portfolio analysis dashboard [MS 7]
**Story:** As a beginner investor, I want to upload my holdings and see my portfolio at a glance, so that I understand its makeup and risk (FR24).

**Acceptance criteria:**
1. The Portfolio tab accepts a CSV upload in the D-29 format and has a button to load a sample portfolio (Story 2.4).
2. It shows the Story 3.3 metrics: total value, weighted expense ratio, diversification score and risk assessment.
3. It shows a pie chart of holdings and a bar chart of allocation by asset type (FR27).
4. It shows a holdings table with each price's freshness label.
5. Upload problems are listed clearly (Story 3.3, AC 1).
6. The agent's plain-language explanation appears with the metrics, with a disclaimer on any recommendation (D-7).

#### Story 7.3: Add market overview visualizations [MS 7]
**Story:** As a beginner investor, I want a quick view of the market, so that I can connect what I learn to real prices (FR25).

**Acceptance criteria:**
1. The Markets tab shows a card for each configured ticker (D-18) with price, change and percent change.
2. Each ticker has a trend line chart from its price history (FR27).
3. A search box looks up any US ticker (D-21).
4. Every figure and chart shows its freshness label (Story 8.4).
5. Refreshing the tab uses the cache and never exceeds the API limits (Story 8.2, Story 8.3).

#### Story 7.4 (new): Goals tab [D-4, GAP-6]
**Story:** As a beginner investor, I want a simple form to plan a savings goal, so that I can see my plan without typing it into chat.

**Acceptance criteria:**
1. The Goals tab has fields for target amount, target date and current savings, and uses the sidebar risk tolerance (Story 5.5).
2. It shows the required monthly saving and a goal projection chart (FR27), using the same calculations as the Goal Planning Agent (Story 4.1).
3. It states the assumed annual return and that results are estimates, with a disclaimer where it applies (D-7).
4. Invalid inputs show a clear message next to the field (Story 4.1, AC 6).

#### Story 7.5 (new): Accessibility, branding and responsive design [GAP-6, NFR9]
**Story:** As a beginner investor, I want the app to be easy to read and use on my device, so that nothing gets in the way of learning.

**Acceptance criteria:**
1. The app is branded "Finnie" [PB] and uses Streamlit's default theme. No other branding is required in v1.
2. Every chart has a title, labeled axes or a legend, and plain-language labels [FAQ UI 2].
3. Chart data is also available as a table, so it doesn't rely on color alone.
4. The layout works at laptop and tablet widths (NFR9).
5. No formal accessibility standard (such as WCAG) is targeted in v1.

### Epic 8: Real-time Data Integration [MS 8]
*Build order: 4th (D-31).*

> **Approved by the PM (D-35).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2, GAP-3 and GAP-5. Story titles 8.1–8.4 are source wording. Stories 8.5–8.6 are new stories for news search (FR5, D-10) and mock data (D-18), which no milestone covered.

**Epic goal:** Give agents dependable market and news data within the free API limits: live data when available, cached or labeled sample data when not, so the app and the demo never break because of an API limit or outage ([PB]: "the #1 demo killer").

#### Story 8.1: Integrate Alpha Vantage API [MS 8]
**Story:** As a beginner investor, I want to look up current prices and recent trends for US stocks and funds, so that I can see real examples of what I'm learning (FR15, FR16).

**Acceptance criteria:**
1. An async client (D-17) fetches a quote for a US ticker (D-21): price, change, percent change, volume and the time of the quote.
2. The client fetches daily price history for trend lines (FR27).
3. The API key comes from configuration (D-25).
4. An unknown ticker returns a clear "ticker not found" result, not an error.
5. The Markets tab's 3–5 tickers (D-18) are set in configuration.
6. How fresh the free tier's quotes are (real-time, delayed or end-of-day) is checked against Alpha Vantage's own documentation and recorded in the technical design document (D-42).

#### Story 8.2: Implement caching strategy [MS 8]
**Story:** As the Finnie developer, I want API results cached, so that the app stays within free limits and responds quickly (NFR3).

**Acceptance criteria:**
1. Market data is cached per ticker and data type. Quotes use a 30-minute TTL (NFR3). Daily price history uses a 24-hour TTL, since it changes only once a day (D-41). Both are set in configuration.
2. A cache hit within the TTL makes no API call (verified by test).
3. The cache is saved to disk so restarting the app does not use up the daily limit again.
4. Every cache entry stores the time it was fetched, for freshness labels (Story 8.4).

#### Story 8.3: Handle rate limits and failures [MS 8]
**Story:** As a beginner investor, I want the app to keep working when a data service is down or out of requests, so that I'm never stuck with an error (NFR4).

**Acceptance criteria:**
1. The client counts its own requests against the Alpha Vantage limits (25 per day, 5 per minute [PB]) and does not call the API once a limit is reached.
2. Alpha Vantage's rate-limit responses (which can arrive as a normal response with a notice instead of data) are detected and treated as failures.
3. Temporary failures are retried with exponential backoff, up to a configured number of attempts [FAQ Tech 4].
4. When live data is unavailable, the fallback order is: cached data (D-9), then mock data (D-18). The user never sees a raw error.
5. Every failure and fallback is logged (Story 1.6).

#### Story 8.4: Add data freshness indicators [MS 8]
**Story:** As a beginner investor, I want to know whether the data I'm seeing is live, cached or sample data, so that I don't mistake old or fake numbers for real ones (FR17, D-24).

**Acceptance criteria:**
1. Every market data result carries one of three labels: **Live**, **Cached** (with its age, for example "updated 12 min ago") or **Sample data**. Live and cached quotes also show the quote's own timestamp from Alpha Vantage (for example, "as of market close"), not just when it was fetched (D-42).
2. News results carry the same labels (D-8, D-11).
3. Tests confirm the correct label for each of the three sources.

#### Story 8.5 (new): News search via SerpApi [FR5, D-10]
**Story:** As a beginner investor, I want current financial news with sources, so that I can see how what I'm learning applies right now.

**Acceptance criteria:**
1. An async client (D-17) searches SerpApi for US financial news (D-21) and returns each item's headline, source, link and date.
2. News results are cached (D-8) with a configurable TTL, default 6 hours, to stay within SerpApi's 100 requests per month [PB].
3. The client counts its monthly requests and stops calling SerpApi once the limit is reached.
4. On failure, the fallback order is cached news (D-9), then mock news (D-8). Tavily is not used as a fallback (D-9).
5. Tavily is optional (D-14). If implemented, it is selected only through configuration, and its results are cached too (D-11).

#### Story 8.6 (new): Mock data set [D-18]
**Story:** As the Finnie developer, I want realistic sample data for every external service, so that the app and the demo work even with no API access.

**Acceptance criteria:**
1. Mock quotes and price history exist for the configured Markets tab tickers and every ticker in the sample portfolios (Story 2.4).
2. Mock news items exist for the News Synthesizer Agent.
3. Mock data is used only as the last fallback (Story 8.3, AC 4; Story 8.5, AC 4) and is always labeled "Sample data" (Story 8.4).
4. A configuration setting can force mock mode, for offline development and tests.

### Epic 9: [Optional] Testing & Quality Assurance [MS 9]
*Build order: 9th (D-31).*
**Decision D-13:** this epic is required. The "[Optional]" label is kept as source wording only.

> **Approved by the PM (D-40).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2 and GAP-3. Story titles 9.1–9.4 are source wording. Each earlier story already includes its own tests; this epic closes the gaps and checks the system as a whole.

**Epic goal:** Prove Finnie works as a whole: at least 80% test coverage (D-13), end-to-end integration tests, a user acceptance run of the demo scenarios, and measured performance against the targets in NFR13.

#### Story 9.1: Write comprehensive unit tests [MS 9]
**Story:** As the Finnie developer, I want thorough unit tests, so that changes don't silently break anything (NFR6).

**Acceptance criteria:**
1. `pytest` with coverage reports at least 80% line coverage overall and fails the run below 80% (D-13).
2. Unit tests cover every agent, the router, RAG retrieval, the market and news clients, caching, fallbacks, and error handling [FAQ T&D 1].
3. Edge cases are covered, including malformed queries, malformed uploads and API limit responses [FAQ T&D 1].
4. Unit tests make no real API calls; they use mocks or mock mode (Story 8.6).

#### Story 9.2: Implement integration tests [MS 9]
**Story:** As the Finnie developer, I want end-to-end tests through the full workflow, so that I know the parts work together.

**Acceptance criteria:**
1. Integration tests send questions through the whole path: router, agent, retrieval or data client, and response with sources, labels and disclaimers.
2. They include the six-agent multi-turn conversation (Story 4.4) and a portfolio upload through to the dashboard data.
3. They run with mocked external APIs by default.
4. An optional live smoke test, switched on by a flag, makes a small number of real API calls so it doesn't exhaust the free limits.

#### Story 9.3: Conduct user acceptance testing [MS 9]
**Story:** As the PM, I want to try the app against a written script, so that I can confirm it does what beginners need before the demo.

**Acceptance criteria:**
1. A UAT script in `docs/` covers the demo scenarios [PS §5]: multi-turn conversations with different agents, portfolio analysis, market data and goal planning.
2. The script also checks disclaimers on advice (D-7), freshness labels (D-24) and behavior when an API limit is reached.
3. The PM runs the script; results and issues are recorded in `docs/`.
4. All issues the PM marks as blocking are fixed and re-tested.

#### Story 9.4: Performance optimization [MS 9]
**Story:** As a beginner investor, I want Finnie to respond quickly, so that learning feels like a conversation, not a wait.

**Acceptance criteria:**
1. A benchmark script measures every target in NFR13.
2. Results are saved in `docs/` as the performance benchmarks deliverable [PS §5].
3. Any target that is missed is either fixed or recorded with its cause and agreed with the PM.

### Epic 10: Documentation & Deployment [MS 10]
*Build order: 10th (D-31).*

> **Approved by the PM (D-40).** The goal, story statements and acceptance criteria were drafted to fill GAP-1, GAP-2 and GAP-3. Story titles 10.1–10.4 are source wording.

**Epic goal:** Make Finnie easy for evaluators to understand, run and judge: complete documentation, a demo video, deployment artifacts, and a final polish pass.

#### Story 10.1: Create comprehensive documentation [MS 10]
**Story:** As an evaluator, I want complete documentation, so that I can understand, set up and use Finnie without help.

**Acceptance criteria:**
1. The README includes an architecture overview, setup instructions, API documentation, usage examples and a troubleshooting guide [PS §5].
2. The technical design document (started in Story 1.3) is complete: system architecture decisions, agent communication protocols, RAG implementation details and performance considerations [PS §5], with architecture diagrams [FAQ T&D 2].
3. Technology choices and their reasoning are documented [FAQ Sub 2].
4. Public functions and classes have docstrings [PS §6: inline documentation].

#### Story 10.2: Record demo video [MS 10]
**Story:** As an evaluator, I want a short demo video, so that I can see Finnie's main features working.

**Acceptance criteria:**
1. The video is 5–10 minutes long [PS §5].
2. It shows multi-turn conversations with different agents, portfolio analysis, market data integration and a goal planning example [PS §5], and how the agents work together across turns [FAQ Sub 3, D-16].
3. It shows at least one disclaimer on an advice-type answer (D-7) and a freshness label (D-24).
4. It is recorded with caching and mock fallback working, so an API limit can't spoil it [PB].

#### Story 10.3: Prepare deployment artifacts [MS 10]
**Story:** As an evaluator, I want everything needed to run Finnie locally, so that setup is quick and reliable (D-20, NFR12).

**Acceptance criteria:**
1. Environment setup files are included: `.env.example` and `requirements.txt` [PS §5].
2. Sample data for testing is included (Story 2.4) [PS §5].
3. Performance benchmarks are included (Story 9.4) [PS §5].
4. A Dockerfile is included that runs the app locally. Docker is optional in the sources [PS §5] but earns bonus points [FAQ Sub 4].
5. Someone following only the README can run the app from a fresh clone.

#### Story 10.4: Final polish and bug fixes [MS 10]
**Story:** As the PM, I want a final quality pass, so that the submission is clean and stable.

**Acceptance criteria:**
1. All known blocking bugs are fixed.
2. All tests pass, with coverage at or above 80% (D-13).
3. The UAT script (Story 9.3) passes on a final run.

### Epic 11: [STRETCH] MCP Server Implementation [MS 11]
**Epic goal:** n/a
**Decision D-28:** this epic is out of scope for v1. Its stories are kept below as source wording only.

| Story | Title (source wording) | Related requirements | Story statement | Acceptance criteria |
|---|---|---|---|---|
| 11.1 | Build Model Context Protocol server | FR29 | GAP-1 | GAP-2 |
| 11.2 | Integrate with Claude Desktop | FR29 | GAP-1 | GAP-2 |
| 11.3 | Document protocol usage | FR29 | GAP-1 | GAP-2 |

---

## 7. Checklist Results Report

*Run on 2026-10-14 against the standard BMAD PM checklist categories. No BMAD checklist file is installed in this project, so the categories were applied from the standard BMAD method.*

| Category | Status | Notes |
|---|---|---|
| 1. Problem definition and context | PASS | Customer problem [PB], business case [PS §1], target users and non-users (§1.2). |
| 2. MVP scope definition | PASS | Six agents (D-1), four tabs (D-4), local only (D-20), US only (D-21). Out of scope: MCP (D-28) and Future Directions (D-23). |
| 3. User experience requirements | PASS | §3 plus Epic 7; Goals tab, branding and accessibility decided (D-39). |
| 4. Functional requirements | PASS | FR1–FR29, each traced to its source and decisions. |
| 5. Non-functional requirements | PASS | NFR1–NFR14 with performance targets (NFR13). Findings F-1 and F-2 applied (D-41, D-42). |
| 6. Epic and story structure | PASS | 10 v1 epics in an approved build order (D-31); every story has a statement and testable acceptance criteria. Story sizing is left to sprint planning (GAP-4). |
| 7. Technical guidance | PASS | Stack (D-2), LLM (D-6), async (D-17), repo/app structure (D-30), configuration (D-25). Detailed design is assigned to Story 1.3. |
| 8. Cross-functional requirements | PASS | Data sources and fallbacks are defined. Finding F-3 applied (D-43). |
| 9. Clarity and communication | PASS | Every requirement is source-tagged; every decision is logged in §12. |

**Findings (all approved and applied: F-1 → D-41, F-2 → D-42, F-3 → D-43):**
- **F-1: The Alpha Vantage budget is tighter than the stories assume.** A Markets tab ticker needs two calls (a quote and price history), so 5 tickers use 10 of the 25 daily calls per refresh. A user portfolio needs one call per holding, so a 30-holding upload (within the 200-row limit) cannot be fully priced in one day, and Story 8.6 has mock data only for configured and sample tickers. *Recommendation:* cache daily price history for 24 hours (it only changes once a day), and show holdings that have no live, cached or mock price as "price unavailable", excluded from totals with a note.
- **F-2: Free-tier "live" data may not be live.** Third-party sources report that Alpha Vantage's free tier returns delayed or end-of-day US stock data, with real-time data on paid plans. This should be checked on Alpha Vantage's own site. *Recommendation:* if confirmed, the "Live" label (Story 8.4) shows the quote's own timestamp (for example, "as of market close"), not just the fetch time.
- **F-3: Advice detection can miss.** Disclaimers depend on each response being flagged as advice (Story 3.1). If the flag is wrong, an advice-type answer goes out without a disclaimer. *Recommendation:* when the flag is uncertain, treat the response as advice, and include advice-detection cases in the Story 3.1 tests.

## 8. Next Steps

### UX Expert Prompt
Using `docs/prd.md` (Finnie: AI Finance Assistant) as the source of truth, create the front-end specification for a Streamlit app with four tabs (Chat, Portfolio, Markets, Goals; D-4) and a session profile sidebar (Story 5.5). Design for the two personas in §1.2: beginners put off by jargon. Cover each tab's layout and states (empty, loading, error, cached, sample data), how agent names, sources, freshness labels and disclaimers appear in chat (Story 7.1), and the charts listed in FR27 and Story 7.5. Use Streamlit's default theme; no formal WCAG target in v1 (D-39). Do not add features beyond the PRD.

### Architect Prompt
Using `docs/prd.md` (Finnie: AI Finance Assistant) as the source of truth, create the architecture and the technical design document required by Story 1.3. Fixed decisions: LangGraph/LangChain, OpenAI `gpt-4o-mini` via `OPENAI_MODEL`, FAISS with all-MiniLM-L6-v2, Streamlit, async Python (D-2, D-6, D-17); Alpha Vantage and SerpApi, with Tavily optional (D-10, D-14); single repo and single app in the prescribed structure (D-30); local deployment (D-20). Define the router and single-agent dispatch (D-16), the six agents' inputs and outputs, the session-only state (D-15), retrieval when needed (D-22), caching, rate limits, fallbacks and freshness labels (Epic 8), disclaimer handling (D-7), the async–Streamlit boundary, and the diversification, risk and goal-projection formulas. Follow decisions D-41 to D-43 (checklist findings F-1 to F-3). Do not add features beyond the PRD.

---

## 9. Gaps: Needed by BMAD, Not in Source

- **GAP-1: RESOLVED (D-32 to D-40).** User-story statements. No story has an "As a / I want / so that" statement. The source milestones are task lists.
- **GAP-2: RESOLVED (D-32 to D-40).** Acceptance criteria. No acceptance criteria exist for any story. The evaluation criteria [PS §6] are grading weights, not testable criteria.
- **GAP-3: RESOLVED (D-32 to D-40).** Epic goal statements. Milestones have titles only, with no goal or expected outcome.
- **GAP-4: RESOLVED for order (D-31); sizing left to sprint planning.** Epic sequencing and sizing. BMAD normally sequences epics so each one delivers a deployable, testable increment. The milestone order puts research first and the UI in Epic 7. Confirm whether to keep the source order. Story sizing and dependencies are not given. [PB] "mock data fallbacks early" implies caching and mock data should come before Epic 8; confirm.
- **GAP-5: RESOLVED.** Each item now has a story: personalization → 5.5; disclaimers and LLM rate limiting → 3.1; category filtering → 6.5; trend analysis → 3.4; news search → 8.5; holdings upload → 3.3, 7.2; logging → 1.6; async → 3.1, 5.1, 6.3, 8.1, 8.5; benchmarks → 9.4, 10.3; environment setup files → 10.3; technical design document → 1.3, 10.1; yFinance removed by D-2. Original gap: Requirements with no milestone/story. These requirements appear in the sources, but no milestone covers them, so no story exists for them:
  - FR12 personalization (knowledge level, goals, risk tolerance) and user-profile capture
  - FR28 education-vs-advice disclaimers
  - FR19 "category-based filtering for targeted responses" (MS 2 only covers structuring content by category)
  - FR16 "market trend analysis and insights" (only implied by Story 3.4)
  - FR5 news search integration (SerpApi per D-10; caching per D-8/D-11; cache fallback per D-9)
  - FR13 holdings upload [PB]
  - NFR1 logging ("Proper error handling and logging throughout")
  - NFR5 LLM rate limiting
  - NFR14 async Python throughout [PB]
  - §2.3 performance benchmarks, environment setup files, technical design document. These may fall under Stories 10.1/10.3, but the source doesn't say so.
- **GAP-6: RESOLVED (D-39: Stories 7.4, 7.5).** UI details. No accessibility standard. No branding beyond the name "Finnie". No description of the Goals tab.
- **GAP-7: RESOLVED (D-40, §1.2).** Target users. [PB] gives a customer problem ("Most adults want to invest… beginners"), but there are no personas, segments or user journeys.
- **GAP-8: RESOLVED (D-40, NFR13).** Measurable NFR targets. There are no targets for response latency, throughput, concurrency or uptime, yet performance benchmarks are a required deliverable.
- **GAP-9: RESOLVED (D-29).** Portfolio input. [PB] says holdings are "uploaded", but no file format, fields or size limit is given.
- **GAP-10: RESOLVED (D-30).** Repository and service architecture. Repository type and monolith vs. services are not stated.

## 10. Questions for the PM: Unclear, Contradictory or Risky (not changed)

- **Q-1: RESOLVED (D-1).** How many agents are required? "Implement all six" [PS §3], "at least above mentioned working agents" [PS §5] and "Six specialist agents collaborate" [PB] vs. "at least 4-5 agents" [FAQ Tech 3]. The milestones also mark News as "if time permits" and Tax as "stretch goal" [MS 4].
- **Q-2: RESOLVED (D-13).** Is testing required or optional? "Build comprehensive test suite with 80%+ coverage" is listed as a deliverable [PS §3]. The same suite is "[Optional]" in Submission Guidelines [PS §5] and Milestone 9 [MS 9]. Testing is also graded at 5% [PS §6].
- **Q-3: RESOLVED (D-19).** What is the grading weight for architecture? The FAQ says "The multi-agent architecture and workflow orchestration (40% of grade)" [FAQ Sub 1]. The evaluation table gives Multi-Agent Architecture 10% + LangGraph Workflow 10% = 20%; 40% is the whole Technical Implementation category [PS §6].
- **Q-4: RESOLVED (D-2).** Is the [PB] tech stack the decision? [PB] names one stack: LangGraph, LangChain, OpenAI/Gemini, FAISS, all-MiniLM-L6-v2, Streamlit, Alpha Vantage, SerpApi/Tavily. [PS §2] lists alternatives (CrewAI, Chroma/Pinecone, yFinance, Gradio/React, Claude Sonnet), and [FAQ Sub 2] allows alternatives if documented. Is everything outside the [PB] stack now out?
- **Q-5: RESOLVED (D-18).** How fresh must market data be? It is called "real-time"/"live quotes" [PS §2, §3, §5; PB], but a 30-minute cache TTL is recommended [FAQ Tech 4] and "must" be built [PB]. With Alpha Vantage at 25 requests/day [PB], how many tickers and refreshes must the market tab and demo support?
- **Q-6: RESOLVED (D-3).** Recommendations vs. no advice. Portfolio analysis is graded on "Meaningful metrics and recommendations" [PS §6], and user trust calls for "conservative recommendations" [PS §1]. The FAQ says "avoid specific investment advice" [FAQ Domain 2], and [PB] says the system "explicitly distinguishes education from advice". Where is the line? This is a regulatory risk.
- **Q-7: RESOLVED (D-15).** Do user profiles persist? The system "maintains conversation history and user profiles" and adapts to "knowledge level, goals, and risk tolerance" [PS §1]. But only "simple session-based identification" and Streamlit session state are expected [FAQ UI 3]. Should profiles persist across sessions? How is risk appetite captured?
- **Q-8: RESOLVED (D-20).** Is "thousands of users simultaneously" a requirement or a business aspiration? It sits in the business case [PS §1], while local deployment is "sufficient" [FAQ Sub 4], and the free API quotas in [PB] (for example, 25 Alpha Vantage requests/day) would not support it.
- **Q-9: RESOLVED (D-26).** What does "production-ready" mean here? [PS §3, §4] vs. "MVP" [PS §4], "Local deployment is sufficient" [FAQ Sub 4] and "without too much infrastructure overhead" [PB].
- **Q-10: RESOLVED (D-6).** Which LLM is primary? [PB]: "OpenAI (or Google Gemini as a free alternative)", with OpenAI "Provided by the program". [FAQ Tech 1]: "Google Gemini 2.0 Flash is recommended", with "free tier (60 requests/minute)", which may also be out of date. [PS §2] also lists Claude Sonnet. Which model is primary, and which OpenAI model?
- **Q-11: RESOLVED (D-27).** Where does expense-ratio data come from? Expense ratios are an essential metric [FAQ Domain 3], but no data source is named. It is not clear that Alpha Vantage provides them reliably within its free quota.
- **Q-12: RESOLVED (D-21).** Is the scope US-only? [PB] narrows tax to "401(k) vs IRA vs Roth", which are US account types. Should the whole product (tax, markets, content) be US-only for v1? International markets are listed only as a future direction [PS §7].
- **Q-13: RESOLVED (D-22).** Does every query go through RAG? The data flow puts RAG Retrieval after every agent [PS §2]. Is that intended for the market, portfolio, goal and news agents too, or only for education agents?
- **Q-14: RESOLVED (D-28).** Is MCP bonus or scored? It is labeled [OPTIONAL]/[STRETCH] and described as "Bonus points" [PS §3, MS 11, PS §6], yet its 5% is counted inside the 40% Technical Implementation total. [PB] does not mention MCP at all.
- **Q-15: RESOLVED (D-25).** Is configuration optional? "[Optional] Configuration management via YAML/environment variables" [PS §5], yet `config.yaml` is part of the prescribed structure [PS §5]. API keys for OpenAI, Alpha Vantage and SerpApi/Tavily [PB] will need configuration either way.
- **Q-16: RESOLVED (D-23).** Should Future Directions be treated as explicit out-of-scope (non-goals) for this version? [PS §7] See Appendix B.
- **Q-17: RESOLVED (D-24).** Should mock data be labeled? The FAQ and [PB] call for mock-data fallbacks [FAQ Tech 4, PB]. Should mock market data be clearly labeled to users so it is not mistaken for real prices? (This relates to FR17 data freshness.)
- **Q-18: RESOLVED (D-4).** Four tabs or five? [FAQ UI 1] "3-4 main tabs (Chat, Portfolio, Market, Goals)" vs. [PB] "Chat, Portfolio, Markets, Goals, and Knowledge". What is the Knowledge tab for (browsing articles, the glossary, or something else)? Also, is it "Market" or "Markets"?
- **Q-20: RESOLVED (D-12).** What is the role of the "complete reference implementation"? [PB] says one is provided. Given this is a fresh start, should it be used, consulted only, or ignored?
- **Q-21: RESOLVED (D-5).** SerpApi or Tavily for news? [PB] names both, and their free quotas differ (100/mo vs. 1,000/mo). Neither appears in the [PS] architecture table.
- **Q-22: RESOLVED (D-16).** One agent or several per query? The router "dispatches it to the right agent" [PB] vs. "decide which agent(s) to invoke" [FAQ Tech 2], "Appropriate Agent(s)" [PS §2] and "Show how agents work together" [FAQ Sub 3]. Must one query be able to call several agents?
- **Q-23: RESOLVED (D-17).** Async Python with Streamlit. [PB] requires "async Python throughout", but Streamlit runs scripts synchronously by default, so async needs deliberate handling there. Is "throughout" a hard requirement for the UI layer too, or for agents and API calls only?

- **Q-24: RESOLVED (D-7).** Does D-3 apply to tax? D-3 allows advice or recommendations with a disclaimer. [PB] says the Tax Education Agent explains account types "without giving tax advice". Does the tax agent stay education-only, or may it also give advice with a disclaimer? The same applies to the FAQ's "avoid specific investment advice" [FAQ Domain 2]: is it now replaced by D-3?
- **Q-25: RESOLVED (D-8).** SerpApi quota. With D-5, news search is limited to 100 requests/month on the free tier [PB]. Should news results be cached, with a mock fallback, the same way as market data?

- **Q-26: RESOLVED (D-9, D-10).** How do SerpApi and Tavily work together?
- **Q-27: RESOLVED (D-11).** Should Tavily be cached? D-8 says Tavily results are not cached. D-9 says news falls back to cache when the provider fails. If Tavily is not cached, there is nothing to fall back to when Tavily fails. Should Tavily also be cached for fallback, or just not cached as a performance measure?

- **Q-28: RESOLVED (D-14).** What is Tavily's role? News search uses SerpApi (D-10), and Tavily is not a fallback (D-9). Earlier, Tavily was allowed and its key will be provided (D-5). When, if ever, is Tavily called (for example, an alternative selected by configuration), or is it unused in v1?

*(Q-19 is not used: it was merged into Q-10.)*

## 11. Placement and Interpretation Log

- **INTERP-1:** Milestones were mapped to epics and milestone bullets to stories. The source does not call them epics or stories. [PB] does not define milestones, so the epic list still comes only from the FAQ document.
- **INTERP-2:** Where several source statements describe the same requirement (for example, deliverables plus milestones plus FAQ plus [PB]), they were combined into one FR/NFR with all source quotes kept, not split.
- **INTERP-3:** FR vs. NFR classification is mine. For example, disclaimers (FR28) are classed as functional, and caching/rate limits/async as non-functional.
- **INTERP-4:** Learning Goals [PS §4] are placed under Goals (§1.3). They describe builder outcomes, not product goals.
- **INTERP-5:** Submission Guidelines [PS §5] are kept as a single "Submission Deliverables" block (§2.3). BMAD has no matching section.
- **INTERP-6:** Evaluation Criteria [PS §6] and Resources & References [FAQ] have no BMAD section. They are kept verbatim in the appendices. BMAD success metrics were not derived from them.
- **INTERP-7:** The "Web Responsive" platform in §3.6 combines "web interface" with "responsive design". The §3.3 screen list shows both tab sets without choosing one.
- **INTERP-8:** "Prepare sample portfolio data for testing" (Story 2.4) was kept in the Knowledge Base epic where the source puts it, although it relates to portfolio analysis and test data.
- **INTERP-9:** [PB]'s Customer Problem is placed in Background Context next to [PS §1]'s Business Use Case. Both are kept, not merged.
- **INTERP-10:** The product name "Finnie" from [PB] is used in the document title, alongside the source name "AI Finance Assistant".
- **INTERP-11:** [PB]'s External APIs table is placed under Technical Assumptions (§4.2). Its free-tier quotas are also referenced in NFR4.

## 12. Decisions Log

Decisions made by the PM. Source quotes elsewhere in this PRD are left unchanged; these decisions say which reading applies.

| ID | Date | Question | Decision (as given) | Effect |
|---|---|---|---|---|
| D-1 | 2026-10-14 | Q-1 | "6 agents" | All six agents are required. The "if time permits" (News) and "stretch goal" (Tax) labels in [MS 4] and the "at least 4-5" guidance in [FAQ Tech 3] no longer apply. |
| D-2 | 2026-10-14 | Q-4 | "yes" | The [PB] tech stack is the decision. CrewAI, Chroma DB, Pinecone DB, yFinance, Gradio and React are out. The LLM is set by D-6. |
| D-3 | 2026-10-14 | Q-6 | "provide a disclaimer when providing advice or recommendations" | Advice and recommendations may be given, and each must carry a disclaimer. Open follow-up: Q-24. |
| D-4 | 2026-10-14 | Q-18 | "skip knowledge tab"; "tab should be Markets" | Tabs are Chat, Portfolio, Markets, Goals. |
| D-5 | 2026-10-14 | Q-21 (answered as "Q-20") | "SerpApi"; then "you can use Tavily also, I will provide the api key for both" | News search may use both SerpApi and Tavily. The PM provides both API keys. Applied to Q-21, since these are the news options. Q-20 was answered separately (D-12). Open follow-up: Q-26. |
| D-6 | 2026-10-14 | Q-10 | "Openai model - OPENAI_MODEL=gpt-4o-mini" | The LLM is OpenAI `gpt-4o-mini`, set through `OPENAI_MODEL`. |
| D-7 | 2026-10-14 | Q-24 | "you can provide advice but you must provide disclaimer with advice type responses" | All agents, including Tax, may give advice. Every advice-type response must include a disclaimer. Replaces "avoid specific investment advice" [FAQ Domain 2] and "without giving tax advice" [PB]. |
| D-8 | 2026-10-14 | Q-25 | "if using SerpApi yes, because of 100 requests limit/month, not if using Tavily" | SerpApi news results are cached with a mock fallback. Tavily results are not. (The Tavily part is replaced by D-11.) |
| D-9 | 2026-10-14 | Q-26 | "no it is not a fallback. It should fallback to cache." | SerpApi and Tavily are not fallbacks for each other. When a news request fails, it falls back to cached results. |
| D-10 | 2026-10-14 | Q-26 | "use SerpAPI" | News search uses SerpApi. Open follow-up: Q-28 (Tavily's role). |
| D-13 | 2026-10-14 | Q-2 | "tests are required" | The test suite is required, with 80%+ coverage [PS §3]. The "[Optional]" labels in [PS §5] and [MS 9] no longer apply. |
| D-14 | 2026-10-14 | Q-28 | "doesnt have to be used" | Tavily is optional and need not be integrated in v1. If it is used, its results are cached (D-11). |
| D-15 | 2026-10-14 | Q-7 | "no" | User profiles do not persist across sessions. Conversation history, knowledge level, goals and risk tolerance are kept only for the current session. |
| D-16 | 2026-10-14 | Q-22 | "no" | The router sends each query to one agent. "Show how agents work together" [FAQ Sub 3] is then shown through multi-turn conversations that move between agents. |
| D-17 | 2026-10-14 | Q-23 | "ok async then" | Async Python is adopted, as in [PB]. How async code is called from Streamlit (for example, a thin synchronous bridge at the UI boundary) is left to the architecture document. |
| D-18 | 2026-10-14 | Q-5 | "ok" (to option b) | The Markets tab shows 3–5 stocks. When the Alpha Vantage daily limit (25 requests) runs out, mock data is used and labeled (D-24). |
| D-19 | 2026-10-14 | Q-3 | "40%" | The FAQ's weighting applies: the multi-agent architecture and workflow orchestration are treated as 40% of the grade and are the top build priority. |
| D-20 | 2026-10-14 | Q-8 | "local deployment" | v1 is deployed locally. "Serve thousands of users simultaneously" [PS §1] is a business aspiration, not a v1 requirement. |
| D-21 | 2026-10-14 | Q-12 | "US only" | v1 is US-only: tax content, markets and educational content. |
| D-22 | 2026-10-14 | Q-13 | "if needed" | RAG retrieval runs only when the agent handling the query needs it, not on every query. |
| D-23 | 2026-10-14 | Q-16 | "yes" | Everything in Future Directions [PS §7] (Appendix B) is out of scope for v1. |
| D-24 | 2026-10-14 | Q-17 | "sure" | Cached and mock data are clearly labeled for users so they are not mistaken for live data. |
| D-25 | 2026-10-14 | Q-15 | "why would config be ooptional?" | Recorded as: configuration management is required, via `config.yaml` and environment variables. The "[Optional]" label in [PS §5] no longer applies. |
| D-26 | 2026-10-14 | Q-9 | "production-quality" | "Production-ready" means production-quality code running locally: error handling, logging, tests (D-13), configuration (D-25) and full documentation. User logins, cloud hosting, monitoring and scaling are not v1 requirements. |
| D-27 | 2026-10-14 | Q-11 | "a & b" | Expense ratios come from the uploaded holdings file, with a built-in table of common funds as a backup. |
| D-28 | 2026-10-14 | Q-14 | "please skip" | The MCP server (FR29, Epic 11) is not built in v1. |
| D-29 | 2026-10-14 | GAP-9 | "approve" | Holdings are uploaded as a CSV file with columns `ticker`, `shares`, and an optional `expense_ratio`. |
| D-30 | 2026-10-14 | GAP-10 | "approve" | Single repository, single application, following the prescribed structure (§4.1). |
| D-31 | 2026-10-14 | GAP-4 | "approve" | Epic build order approved, as shown in §5. |
| D-32 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-5 (Epic 1) | "approve" | Epic 1 goal, story statements, acceptance criteria and new Stories 1.5–1.7 approved. |
| D-33 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-5 (Epic 2) | "approve" | Epic 2 goal, story statements, acceptance criteria and new Story 2.5 approved. |
| D-34 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-5 (Epic 6) | "approve" | Epic 6 (RAG) goal, story statements, acceptance criteria and new Story 6.5 approved. |
| D-35 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-5 (Epic 8) | "Approve" | Epic 8 (Real-time Data) goal, story statements, acceptance criteria and new Stories 8.5–8.6 approved. |
| D-36 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-5 (Epic 3) | "Approve" | Epic 3 (Core Agents) approved, including the asset-type column added to Story 2.5. |
| D-37 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-5 (Epic 5) | "Approve" | Epic 5 (Workflow Orchestration) goal, story statements, acceptance criteria and new Story 5.5 approved. |
| D-38 | 2026-10-14 | GAP-1, GAP-2, GAP-3 (Epic 4) | "Approve" | Epic 4 (Advanced Agents) goal, story statements and acceptance criteria approved. |
| D-39 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-6 (Epic 7) | "Approve" | Epic 7 (User Interface) goal, story statements, acceptance criteria and new Stories 7.4–7.5 approved, including Streamlit default theme and no formal WCAG target in v1. |
| D-40 | 2026-10-14 | GAP-1, GAP-2, GAP-3, GAP-7, GAP-8 | "Approve" | Epics 9 and 10 (including the Dockerfile and PM-run UAT), the target-user personas and non-users, and the NFR13 performance targets approved. |
| D-41 | 2026-10-14 | Checklist F-1 | "Approve F-1 to F-3" | Daily price history is cached for 24 hours. Holdings with no live, cached or mock price show "price unavailable" and are left out of totals with a note (Stories 8.2, 3.3). |
| D-42 | 2026-10-14 | Checklist F-2 | "Approve F-1 to F-3" | Quotes show their own Alpha Vantage timestamp, and free-tier freshness is checked and documented (Stories 8.1, 8.4). |
| D-43 | 2026-10-14 | Checklist F-3 | "Approve F-1 to F-3" | Uncertain responses are treated as advice and get a disclaimer; advice detection is tested (Story 3.1). |
| D-12 | 2026-10-14 | Q-20 | "Please ignore it" | The reference implementation mentioned in [PB] is not used or consulted. Finnie is built from scratch from this PRD. |
| D-11 | 2026-10-14 | Q-27 | "should be cached" | Tavily results are cached too. Replaces "Tavily results are not" cached in D-8. |

---

## Appendix A: Evaluation Criteria (verbatim) [PS §6]

**Technical Implementation (40%)**
- Multi-Agent Architecture (10%): Proper implementation of all agents with clean separation of concerns
- LangGraph Workflow (10%): Correct orchestration, state management, and routing
- RAG Implementation (8%): Effective knowledge base indexing and retrieval
- Real-time Data Integration (7%): Robust API integration with proper error handling
- MCP Server (5%): Bonus points for Claude Desktop integration

**User Experience & Interface (25%)**
- Streamlit Application (10%): Multi-tab interface with responsive design
- Conversational Flow (8%): Natural interactions with context preservation
- Data Visualization (7%): Clear, informative charts and displays

**Financial Domain Knowledge (20%)**
- Educational Content (8%): Comprehensive, accurate financial information
- Portfolio Analysis (7%): Meaningful metrics and recommendations
- Market Intelligence (5%): Relevant real-time insights

**Code Quality & Documentation (15%)**
- Code Organization (5%): Modular architecture with clean code
- Documentation (5%): Comprehensive README and inline documentation
- Testing (5%): Thorough test coverage with edge cases

## Appendix B: Future Directions (verbatim) [PS §7]

"The AI Finance Assistant provides a foundation for numerous enhancements:" **Decision D-23:** everything in this appendix is out of scope for v1.

**Advanced Features:** Voice Interface: Natural speech interaction for accessibility · Mobile Application: Native iOS/Android apps for on-the-go access · Advanced Analytics: Monte Carlo simulations, risk modeling · Social Features: Community learning, peer comparisons · Automated Investing: Integration with brokerage APIs

**Technical Enhancements:** Multi-Modal Input: Chart analysis, document parsing · Personalization Engine: ML-based recommendation system · Distributed Architecture: Microservices for scalability · Real-time Collaboration: Multi-user portfolio planning

**Market Expansion:** International Markets: Support for global exchanges · Cryptocurrency Integration: Digital asset education and analysis · Small Business Tools: Expand to business financial planning · Educational Partnerships: Integration with finance courses

**AI Advancements:** Fine-tuned Models: Domain-specific LLM training · Behavioral Analysis: Predict and address user biases · Explainable AI: Transparent decision-making processes · Continuous Learning: System improvement from user interactions

## Appendix C: Resources & References (verbatim) [FAQ]

**Technical Resources:** LangChain Documentation · LangGraph Guide · Streamlit Documentation · FAISS Documentation · yfinance API · Alpha Vantage API

**Financial Education Resources:** Investopedia for concept definitions · Bogleheads wiki for investment principles · SEC investor.gov for regulatory guidance · Modern Portfolio Theory basics
