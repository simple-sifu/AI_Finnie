# Research Note: Multi-Agent Patterns in LangGraph and LangChain

*Story 1.2 (PRD Epic 1). Written 2026-10-14.*

## Purpose

This note records how Finnie will use LangGraph and LangChain for routing, state and async execution, and why LangGraph was chosen over CrewAI (PRD D-2). It informs the workflow design in [`architecture.md`](../architecture.md) §6–§7 and §10.

**Caveats:** this is based on third-party tutorials, framework comparisons and the langchain-openai source code. Some API details, marked **verify** below, were not confirmed against current official documentation. Story 1.4 pins exact library versions, and a small test there confirms each verify item before the workflow is built.

## 1. Routing with `StateGraph`

**How LangGraph routing works**
- A graph is built from **nodes**, which are functions that read the state and return updates to it, and **edges**, which decide which node runs next.
- **Conditional routing:** `add_conditional_edges(source, routing_fn, mapping)`. After the source node runs, `routing_fn` reads the state and returns a label, and `mapping` translates the label into the next node. [langchain-skills: LangGraph fundamentals](https://www.claudepluginhub.com/skills/langchain-ai-langchain-skills/langgraph-fundamentals), [Simplified Guide: conditional routing](https://www.simplified.guide/_export/xhtml/langgraph/graph-add-conditional-route)
- **Pitfall:** a node should use one routing mechanism. If a node has both a normal edge and a conditional edge going out, both paths can be scheduled. [Simplified Guide](https://www.simplified.guide/_export/xhtml/langgraph/graph-add-conditional-route)

**How Finnie applies it** (architecture §6.1)
- The `route` node calls the LLM to classify the query. A routing function then returns the label (`finance_qa`, `portfolio`, `market`, `goal_planning`, `news`, `tax`, `clarify` or `off_topic`), and the mapping sends it to exactly one agent node (D-16).
- Every agent node has a single normal edge to `finalize`. Only `validate_input` and `route` use conditional edges, which avoids the pitfall above.

## 2. Structured LLM Output for Classification

- `ChatOpenAI.with_structured_output(Schema)` returns an instance of a Pydantic class, validated against its fields. Its default method uses OpenAI's Structured Outputs (`json_schema`); `function_calling` and `json_mode` are alternatives. [langchain-openai source](https://git.blob42.xyz/Archives/langchain/src/commit/236e957abbe2f8dcfdb4da102aa6dd43e77b7050/libs/partners/openai)
- Older helpers such as `create_structured_output_chain` are deprecated in favor of `with_structured_output()`. [LangChain reference](https://reference.langchain.com/v0.3/python/langchain/chains/langchain.chains.openai_functions.base.create_structured_output_chain.html)
- **Use in Finnie:** the router's decision (`route`, `confidence`, `clarifying_question`) and each agent's `response_type` (advice, education or uncertain) are structured outputs. This makes routing and the disclaimer policy (architecture §7.4) testable and avoids parsing free text.
- **Verify:** that `await structured_llm.ainvoke(...)` returns the Pydantic instance with the pinned version. The sources show only the synchronous `invoke`.

## 3. State Management

- LangGraph state is a typed object (`TypedDict` or Pydantic). Each node returns only the fields it changes, and LangGraph merges them. [langchain-skills](https://www.claudepluginhub.com/skills/langchain-ai-langchain-skills/langgraph-fundamentals)
- LangGraph can save state after each step with a **checkpointer**, which allows resuming a run and human-in-the-loop steps. [Morph: LangGraph vs CrewAI](https://www.morphllm.com/comparisons/langgraph-vs-crewai), [Fast.io: LangGraph vs CrewAI](https://fast.io/resources/langgraph-vs-crewai/)
- **Use in Finnie:** no checkpointer (architecture §6.3). State is session-only (D-15), and Streamlit's session state already holds the conversation, so each graph run receives the recent history as input. A checkpointer would add a second copy of the state without a v1 need.

## 4. Async Execution

- Nodes can be `async def` functions that `await` other calls and return a partial state update. [langchain-skills](https://www.claudepluginhub.com/skills/langchain-ai-langchain-skills/langgraph-fundamentals)
- A compiled graph is run asynchronously with `await graph.ainvoke(state)`. **Verify** with the pinned version; the sources reviewed did not show a full example.
- **Use in Finnie** (D-17, architecture §10):
  - All nodes and agents are async.
  - CPU-bound work (embedding, FAISS search) runs in `asyncio.to_thread` so it doesn't block the event loop.
  - Streamlit calls into the graph through the background event loop, not `asyncio.run()` on each rerun.

## 5. Why LangGraph, Not CrewAI (D-2)

| | LangGraph | CrewAI |
|---|---|---|
| Model | Explicit graph: nodes, edges, conditional routing, loops | A "crew" of role-based agents working through sequential or hierarchical processes |
| Control flow | Precise; the developer decides every path | Higher-level; reviewers say it becomes harder to control precisely |
| State | Typed, explicit state object, with optional checkpointing | Managed by the crew's task pipeline or Flows |
| Best for | Production workflows that need predictable routing, fallbacks and state | Fast prototyping of agents that collaborate on a task |

Sources: [Morph](https://www.morphllm.com/comparisons/langgraph-vs-crewai), [Fast.io](https://fast.io/resources/langgraph-vs-crewai/), [Spheron](https://www.spheron.network/blog/langgraph-vs-crewai-vs-autogen-2026/), [AppliPlus](https://appliplus.com/blog/langchain-vs-langgraph-vs-crewai). These are blog and vendor comparisons, not benchmarks.

**Why LangGraph fits Finnie:**
1. **Predictable routing.** Each question goes to exactly one agent (D-16), with defined clarify, off-topic and fallback paths (Story 5.1, Story 5.3). An explicit graph expresses this directly. A collaborative crew would decide its own steps.
2. **Guaranteed final step.** Every response passes through `finalize`, so disclaimers (D-7, D-43) and freshness labels (D-24) can't be skipped.
3. **Speed and cost.** One router call plus one agent call per question supports the chat target of a 6-second median (NFR13). Crew-style collaboration typically adds more LLM calls.
4. **Grading.** The evaluation criteria score "LangGraph Workflow (10%)" specifically (PRD Appendix A), and the FAQ recommends `StateGraph` [FAQ Tech 2].

## 6. Patterns Finnie Will Avoid

- **Supervisor or agent-to-agent loops,** where agents call each other or a supervisor iterates. These add LLM calls and latency, and D-16 rules out multi-agent dispatch per query.
- **Unbounded tool loops.** Agents that use tools (for example, the knowledge-base tool for Portfolio and Goal Planning, architecture §7.3) get a small maximum number of tool calls.
- **Mixed edge types from one node,** per the pitfall in §1.

## 7. Items to Verify in Story 1.4

1. Pin `langgraph`, `langchain` and `langchain-openai` versions in `requirements.txt`.
2. Confirm `await graph.ainvoke(...)` on a compiled `StateGraph` with async nodes.
3. Confirm `await ChatOpenAI(...).with_structured_output(Model).ainvoke(...)` returns a `Model` instance.
4. Confirm that async LangChain/LangGraph clients work from the background event loop described in architecture §10.
