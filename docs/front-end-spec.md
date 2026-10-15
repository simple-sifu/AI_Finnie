---
title: Finnie — Front-End Specification
status: final
created: 2026-10-14
updated: 2026-10-14
source: docs/prd.md (v1.0)
---

# Finnie: Front-End Specification

This spec turns the UI requirements in [`prd.md`](prd.md) into screen-level detail for the Streamlit app. The PRD is the source of truth. References like (Story 7.1) or (D-24) point to it.

Anything the PRD does not already specify is marked **NEW**. All NEW items were approved by the PM on 2026-10-14.

## 1. UX Goals and Principles

**Users:** beginners who are put off by jargon and afraid of making mistakes (PRD §1.2: Maya, a first-time investor; Daniel, a hesitant self-investor).

**Principles**
1. **Plain language first.** Every label, message and chart title uses everyday words (NFR8).
2. **Show your work.** Answers show which agent replied, where the information came from, and how fresh the data is (Story 7.1, D-24).
3. **Never a dead end.** Errors, API limits and missing data always come with a plain explanation and a way forward (NFR1, Story 5.3).
4. **Simple over polished.** Streamlit's default theme and standard components (D-39). Grading favors system design over UI polish [FAQ Sub 1].

## 2. Information Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Sidebar                 │ Main area                          │
│                         │                                    │
│ Finnie                  │ [ Chat | Portfolio | Markets | Goals ]
│ AI Finance Assistant    │                                    │
│                         │  (content of the selected tab)     │
│ Your profile            │                                    │
│  Knowledge level        │                                    │
│  Risk tolerance         │                                    │
│  Goal note (optional)   │                                    │
│                         │                                    │
│ [New conversation]      │                                    │
│                         │                                    │
│ About Finnie (NEW)      │                                    │
└──────────────────────────────────────────────────────────────┘
```

- **Tabs:** Chat, Portfolio, Markets, Goals, in that order (D-4). Chat is the default tab.
- **Sidebar:** the session profile (Story 5.5) and the "New conversation" action (Story 5.2). It is visible from every tab.
- **About Finnie (NEW):** a short collapsed note: "Finnie is an educational tool. Information is for learning and may be delayed. Advice-type answers include a disclaimer." This gives the education-vs-advice message a permanent home without repeating it on every answer.

## 3. Shared Components

### 3.1 Freshness label (Story 8.4, D-24, D-42)

Shown next to every market or news figure.

| State | Label text | Style (NEW) |
|---|---|---|
| Live | `Live · as of {quote time}` | green dot |
| Cached | `Cached · updated {n} min ago · as of {quote time}` | amber dot |
| Sample data | `Sample data · not real prices` | grey dot, italic |

The colored dot is never the only signal: the word (Live, Cached, Sample data) always appears (Story 7.5, AC 3).

### 3.2 Disclaimer callout (Story 3.1, D-7, D-43)

- Appears under any advice-type answer, visually separate from the answer (Story 7.1, AC 4), using Streamlit's warning style.
- The wording comes from configuration (Story 3.1, AC 4). **Default wording (NEW):** "This is general information for learning purposes, not personalized financial, investment or tax advice. Consider speaking with a licensed professional before making decisions."

### 3.3 Sources list (Story 6.4)

- A collapsed "Sources" section under the answer, listing each source's article title as a link.
- Not shown when the answer used no retrieved content.

### 3.4 Agent badge (Story 7.1, AC 2)

- A small label above each assistant message naming the agent: Finance Q&A, Portfolio Analysis, Market Analysis, Goal Planning, News, Tax Education.

### 3.5 Friendly error message (Story 3.1, AC 5; Story 5.3)

- Plain text in Streamlit's info style, with what happened and what to do next. Never a stack trace. Examples are in §6.

## 4. Screens

### 4.1 Chat tab (Stories 5.1, 5.4, 7.1)

**Layout:** message history (oldest at top), input box pinned at the bottom.

**Assistant message anatomy:**
```
[Agent badge: Market Analysis]
Answer text in plain language...
Freshness label(s) for any figures
[Disclaimer callout — advice-type answers only]
▸ Sources (collapsed — only if retrieval was used)
```

**States**

| State | What the user sees |
|---|---|
| Empty (first visit) | A welcome line and 3–4 example questions as clickable buttons (**NEW**), e.g. "What is compound interest?", "How much should I save each month for a $20,000 goal?", "What's the difference between a 401(k) and a Roth IRA?" |
| Waiting for an answer | A spinner with "Finnie is thinking…" (Story 7.1, AC 5) |
| Clarifying question | The router's question, shown as a normal assistant message (Story 5.1, AC 3) |
| Off-topic question | A polite note on what Finnie can help with (Story 5.1, AC 3) |
| Agent asks for risk tolerance | The question in chat; the sidebar field updates once answered (Story 5.5, AC 2) |
| Error | A friendly message; the input stays usable (Story 5.3) |

### 4.2 Portfolio tab (Stories 3.3, 7.2)

**Layout, top to bottom:**
1. **Upload area:** file uploader for CSV, a one-line format hint ("Columns: ticker, shares, and optional expense_ratio"), and a **Load sample portfolio** button (Story 7.2, AC 1). A selector for which sample to load (**NEW**), since there are at least three (Story 2.4).
2. **Metric tiles (4 across):** Total value · Weighted expense ratio · Diversification score · Risk level (Story 3.3, AC 2).
3. **Charts (2 across):** holdings pie chart; allocation-by-asset-type bar chart (FR27).
4. **Explanation:** the Portfolio Analysis Agent's plain-language summary, with a disclaimer callout if it includes recommendations (Story 7.2, AC 6).
5. **Holdings table:** ticker, shares, price, value, % of portfolio, expense ratio, asset type, freshness label.

**States**

| State | What the user sees |
|---|---|
| Empty | Upload area only, with a short line explaining what the analysis shows |
| Analyzing | A spinner over the metrics area |
| Upload problems | A list of each problem (e.g. "Row 3: shares is not a number") and no analysis (Story 3.3, AC 1) |
| File too large | "This file has more than 200 rows (or is over 1 MB). Please upload a smaller file." (NFR13) |
| Some prices missing | Those rows show "price unavailable"; a note above the tiles says they are left out of totals (D-41) |
| Expense ratio unknown | Shown as "unknown", never 0 (Story 2.5, AC 3) |

### 4.3 Markets tab (Stories 3.4, 7.3)

**Layout:**
1. **Ticker search:** text box for any US ticker (Story 7.3, AC 3).
2. **Ticker cards:** one per configured ticker (3–5, D-18). Each shows price, change, percent change and the freshness label. Up and down moves use both color and an arrow (▲/▼), so color is not the only signal (Story 7.5).
3. **Trend chart:** a line chart of price history for the selected ticker (FR27). Selecting a card shows its chart (**NEW**).
4. **Explain button (NEW):** "Explain this" asks the Market Analysis Agent about the selected ticker and shows its plain-language explanation below the chart, with any disclaimer (Story 3.4, AC 3). It stays on the Markets tab, because Streamlit can't reliably switch tabs from code.

**States**

| State | What the user sees |
|---|---|
| Ticker not found | "We couldn't find that ticker. Check the symbol and try again." (Story 8.1, AC 4) |
| Daily limit reached | Cards show cached or sample data with their labels, plus a note: "Live data is paused until tomorrow to stay within our free data limit." (Story 8.3) |
| Loading | Card placeholders with a spinner |

### 4.4 Goals tab (Stories 4.1, 7.4)

**Layout:**
1. **Form:** target amount ($), target date, current savings ($). Risk tolerance is read from the sidebar and shown read-only, with a link to change it there (Story 7.4, AC 1).
2. **Result:** the required monthly saving in large type, with the assumed annual return beside it and the line "This is an estimate, not a guarantee." (Story 7.4, AC 3).
3. **Projection chart:** year-by-year projected balance against the target as a horizontal line (FR27).
4. Disclaimer callout where it applies (D-7).

**States**

| State | What the user sees |
|---|---|
| Risk tolerance not set | The form shows "Set your risk tolerance in the sidebar to see your plan." and no result |
| Invalid input | A message next to the field, e.g. "The target date must be in the future." (Story 4.1, AC 6) |
| Goal already reached | "Your current savings already meet this goal." |

## 5. Charts (FR27, Story 7.5)

| Chart | Tab | Type | Title (example) | Notes |
|---|---|---|---|---|
| Holdings | Portfolio | Pie | "What you own" | Labels show ticker and %. Up to 8 slices, with the rest grouped as "Other" (**NEW**) |
| Asset-type allocation | Portfolio | Horizontal bar | "Your mix of investments" | Bars sorted largest first; % on each bar |
| Price trend | Markets | Line | "{Ticker}: last 3 months" | Labeled axes (date, price in $); freshness label under the chart |
| Goal projection | Goals | Line, with target line | "Your path to ${target}" | Labeled axes (year, balance in $) |

For every chart:
- A title, labeled axes or a legend, and plain-language labels [FAQ UI 2].
- A "Show as table" toggle with the same data (Story 7.5, AC 3).

## 6. Microcopy (NEW)

All user-facing messages, in one place, so tone stays consistent.

| Situation | Message |
|---|---|
| OpenAI unavailable | "Finnie's assistant is temporarily unavailable. Please try again in a minute." |
| Agent failed | "Sorry, something went wrong answering that. Please try asking again, maybe in different words." |
| No verified content | "I don't have verified information on that topic yet, so I'd rather not guess." |
| Empty input | (Send button disabled; no message) |
| Input too long | "That message is a bit long. Please shorten it to under {limit} characters." |
| No relevant news | "I couldn't find recent news on that. Try a broader topic, like 'stock market today'." |
| New conversation | Confirmation: "Start a new conversation? Your current chat and profile will be cleared." |

## 7. Accessibility and Responsiveness (Story 7.5, NFR9)

- Streamlit default theme. No formal WCAG target in v1 (D-39).
- Color is never the only signal: labels use words, price moves use arrows, and charts have table versions.
- Works at laptop and tablet widths. On narrow screens, Streamlit columns stack vertically. The 4 metric tiles become 2×2 (**NEW**).

## 8. Out of Scope

- A Knowledge tab (D-4)
- User accounts or saved profiles (D-15)
- Custom branding beyond the name "Finnie" (D-39)
- Mobile apps and voice input (D-23)

## 9. Approved Additions

The items marked **NEW** above, all approved by the PM on 2026-10-14:
1. The "About Finnie" sidebar note (§2)
2. Freshness label colors and exact wording (§3.1)
3. The default disclaimer wording (§3.2)
4. Example-question buttons on the empty Chat tab (§4.1)
5. The sample-portfolio selector (§4.2)
6. Selecting a ticker card to show its chart, and the "Explain this" button (§4.3)
7. The 8-slice limit on the holdings pie chart (§5)
8. The microcopy table (§6)
9. Stacking the metric tiles 2×2 on narrow screens (§7)
