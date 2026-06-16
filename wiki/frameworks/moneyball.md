# Moneyball Framework — Probability-Weighted Scenario Scoring

Applied in Section 13 of every full equity thesis. All price targets carry
explicit probabilities that sum to 100%, enabling a calculated expected value
to compare directly against the current price.

---

## Core Formula

```
Expected Value (EV) = (Bull Price × Bull %) + (Base Price × Base %) + (Bear Price × Bear %)
Expected Return     = (EV − Current Price) / Current Price × 100%
Asymmetry Ratio     = Bull Upside % / Bear Downside %
```

A position is compelling when **current price ≤ PW EV − margin of safety** (typ. 15–25% discount to PW EV) per CLAUDE.md Rule #24. Asymmetry Ratio > 2:1 is a useful secondary check but not the primary buy/sell anchor.

---

## Scenario Definitions

### 🐂 Bull Case
- Everything that *could* go right, goes right
- Key assumptions: best-case growth rate, margin expansion, multiple re-rating
- Include terminal math: `[Year] EBITDA $X × [Y]x multiple = $Z/share`
- Typical probability: 20–35%

### Base Case
- Continuation of current trajectory with no major surprise
- Key assumptions: consensus or slight beat, stable multiple
- Include terminal math at the same multiple as bull (or slightly lower)
- Typical probability: 45–60%

### 🐻 Bear Case
- What has to go wrong, and what is the floor?
- Key assumptions: thesis breaks on 1–2 named risks materializing
- Include terminal math: `[Year] EBITDA $X × [Y]x multiple = $Z/share`
- Be specific — the bear case should name the mechanism, not just "macro worsens"
- Typical probability: 15–30%

---

## Template (Section 13)

```
| Scenario | Price Target | Time Horizon | Key Assumptions | Probability |
|----------|-------------|--------------|-----------------|-------------|
| 🐂 Bull  | $X          | 5 years      | [2-3 bullets]   | X%          |
| Base     | $Y          | 5 years      | [2-3 bullets]   | Y%          |
| 🐻 Bear  | $Z          | 5 years      | [2-3 bullets]   | Z%          |

Expected Value: $W
Current Price: $P
Expected Return: +X%
Asymmetry: [Bull upside %] / [Bear downside %] = X:1
```

---

## Asymmetry Assessment (Required)

After the table, always answer:
1. **What must be TRUE for the bear case to materialize?** Is that currently supported by data?
2. **Is the bear case already priced in?** (If stock has already fallen 30%, the bear math changes)
3. **What is the specific catalyst that resolves uncertainty?** (next earnings, FDA decision, etc.)

---

## Wiki Examples

| Ticker | Bull | Base | Bear | EV | Asymmetry | Date |
|--------|------|------|------|----|-----------|------|
| BKNG | $6,200 (30%) | $5,000 (50%) | $3,200 (20%) | $4,900 | 3.1:1 | Mar 2026 |
| WING | $380 (25%) | $290 (55%) | $175 (20%) | $287 | 2.8:1 | Mar 2026 |

*Table updated by LLM agent after each full thesis update.*
