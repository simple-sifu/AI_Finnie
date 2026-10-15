# Research Note: Financial Education Platforms and Robo-Advisors

*Story 1.1 (PRD Epic 1). Written 2026-10-14.*

## Purpose

This note reviews existing services that beginners use to start investing or learn about it. For each one, it records what it offers beginners and where it falls short, then lists what that means for Finnie's design.

**Method and caveats:** details come from third-party reviews published between 2024 and mid-2026 (sources are listed under each platform). Fees and features change often, and some review sites disagree on prices. Exact figures here are approximate and should be checked on each provider's own site before being quoted anywhere user-facing.

## Platforms Reviewed

### 1. Betterment (robo-advisor)

**What it offers beginners**
- Automated investing in diversified portfolios, with a fee of about 0.25% a year. Smaller accounts without regular deposits pay a monthly fee instead (reported as $5/month). [NerdWallet review](https://www.nerdwallet.com/reviews/investing/betterment)
- No account minimum; about $10 to start investing. [NerdWallet comparison](https://www.nerdwallet.com/blog/investing/wealthfront-vs-betterment/)
- An optional premium tier with access to human advisors, which requires about $100,000. Reviews disagree on its price. [Investormint](https://investormint.com/investing/empower-betterment-wealthfront-comparison), [FreedomIsntFree](https://freedomisntfree.co.uk/guides/betterment-vs-wealthfront)

**Where it falls short for beginners**
- It is built to manage money for you, not to teach you. A beginner can invest without learning why a portfolio is built the way it is.
- Talking to a human about concepts sits behind a high balance threshold.

### 2. Wealthfront (robo-advisor)

**What it offers beginners**
- Automated investing at a flat 0.25% a year, with tax-loss harvesting and direct indexing. [Bankrate](https://bankrate.com/investing/betterment-vs-wealthfront)
- Planning tools for goals. [Investormint](https://investormint.com/investing/empower-betterment-wealthfront-comparison)

**Where it falls short for beginners**
- A $500 minimum to start. [NerdWallet](https://www.nerdwallet.com/blog/investing/online-advisor-comparison/)
- No human advisors. [Investormint](https://investormint.com/investing/empower-betterment-wealthfront-comparison)
- As with Betterment, the focus is managing money, not explaining concepts.

### 3. Acorns (micro-investing app)

**What it offers beginners**
- "Round-ups" that invest spare change from purchases into one of five ETF portfolios, by risk level. [Financer](https://www.financer.com/review/acorns)
- A beginner-friendly app with some educational resources. [CNBC Select](https://www.cnbc.com/select/acorns-review/)

**Where it falls short for beginners**
- A monthly subscription (reported from about $3/month) that can take a large share of returns on small balances. [CNBC Select](https://www.cnbc.com/select/acorns-review/)
- Reviewers describe its education as thin, and question whether the paid tiers' learning features are worth the extra cost when similar material is free elsewhere. [DollarSprout](https://dollarsprout.com/acorns-review/)

### 4. Investopedia (education site)

**What it offers beginners**
- A large free library of articles and tutorials, organized by category (stocks, bonds, ETFs and more), plus a stock market simulator for risk-free practice. [Investormint](https://investormint.com/investing/investopedia-academy-review), [SmartAsset](https://smartasset.com/investing/free-investment-classes)
- Paid courses through Investopedia Academy. [Investormint](https://investormint.com/investing/investopedia-academy-review)

**Where it falls short for beginners**
- The material is general. It can't look at your own portfolio or goal and explain what applies to you.
- Beginners have to know what to search for, and articles can still be dense with terms they don't know.

### 5. Khan Academy (education site)

**What it offers beginners**
- Free, short video lessons on finance and investing, described as suitable for absolute beginners. [Noble Desktop](https://www.nobledesktop.com/learn/investing/learn-investing-for-free), [Boredom at Work](https://boredom-at-work.com/best-free-investing-courses/)

**Where it falls short for beginners**
- It is video-first, with less of a structured course path. [Noble Desktop](https://www.nobledesktop.com/learn/investing/learn-investing-for-free)
- It is not connected to live market data or your own situation, and you can't ask follow-up questions.

## Summary

| | Teaches concepts | Personalized to you | Live market context | Ask follow-up questions | Cost to start |
|---|---|---|---|---|---|
| Betterment | Limited | Yes (portfolio) | Your portfolio only | Human advisors at ~$100k | ~$10; fee or 0.25%/yr |
| Wealthfront | Limited | Yes (portfolio) | Your portfolio only | No | $500; 0.25%/yr |
| Acorns | Limited | Yes (risk level) | Your portfolio only | Live Q&A on paid tiers | ~$3/month |
| Investopedia | Yes | No | Separate simulator | No | Free (paid courses optional) |
| Khan Academy | Yes | No | No | No | Free |

**The gap:** robo-advisors and micro-investing apps manage money for beginners but teach relatively little. Education sites teach well but generically, with no link to the learner's own portfolio, goals or live market data, and no way to ask follow-up questions. No service reviewed does all of these at once: explaining concepts in plain language, applying them to the user's own situation, and answering follow-ups in conversation.

## Implications for Finnie

1. **Teach while answering.** Every answer should explain the concept, not just give a number. This supports the PRD's plain-language requirement (NFR8) and the agents' "explain what the numbers mean" role (FR16).
2. **Personal context is the differentiator.** The Portfolio and Goal Planning agents applying concepts to the user's own holdings and goals is what education sites lack (FR12, FR13, FR14).
3. **Live data with teaching attached.** Connecting market data to explanations (Market Analysis, News) bridges theory and practice, as the PRD intends (§1.1).
4. **Follow-up questions are a core feature.** Conversation memory (Story 5.4) lets beginners ask "what does that mean?", which none of the reviewed services offer for free.
5. **Free to use, no minimums.** Fees and minimums are a barrier for beginners with small balances. Finnie has neither (it is a local educational tool).
6. **Trust through sources.** Education sites earn trust by being reputable. Finnie should cite its sources on every knowledge-base answer (FR22) and use reputable sources such as Investopedia and SEC investor.gov (Story 2.1).
7. **Don't become a robo-advisor.** Finnie explains and suggests, with disclaimers on advice (D-7). It does not manage money or place trades (automated investing is out of scope, D-23).
