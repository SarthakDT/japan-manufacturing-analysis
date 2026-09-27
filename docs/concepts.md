# Concepts used in this project

Every statistical, economic, manufacturing and data-engineering idea this project
relies on, explained from first principles, with the equation as it is actually
implemented and a pointer to where it was used.

**How to read an entry.** Each concept has the same four parts:

1. **What it is** — plain language, no prior background assumed.
2. **Equation** — where one exists, every symbol defined.
3. **Worked example** — small enough to check by hand. Examples using project data
   are marked **[real]** and have been verified against `processed_data/`. A few
   toy examples are marked **[illustrative]** and are invented for teaching only.
4. **Where used** — file, notebook or session, and what it decided.

> **Note on H1, H2 and H3.** Several entries below describe concepts that were
> introduced to test three original hypotheses — that specialization raises
> productivity, that aging slows productivity growth, and that diversity raises
> stability. **All three have been retired** and their analysis removed: at n = 47 the
> tests had too little power, none survived correction for multiple comparisons, and
> two of the three measures proved confounded with industry composition. References to
> H1, H2 and H3 below are historical, explaining why a concept entered the project.
> The concepts themselves remain valid and most are reusable. See
> `docs/measurement-framework.md` §4.

Several entries end with a **Pitfall**. In three cases the pitfall is a mistake
this project actually made and corrected; those are the most useful entries here.

---

## Contents

1. [Measuring productivity](#1-measuring-productivity)
2. [Regional and agglomeration economics](#2-regional-and-agglomeration-economics)
3. [Statistics and inference](#3-statistics-and-inference)
4. [Official statistics and data quality](#4-official-statistics-and-data-quality)
5. [Manufacturing domain knowledge](#5-manufacturing-domain-knowledge)
6. [Visualization](#6-visualization)
7. [Index: concept to location](#7-index-concept-to-location)

---

# 1. Measuring productivity

## 1.1 Labour productivity

**What it is.** Output divided by labour input. It answers "how much economic value
does one worker generate?" It is *not* a measure of effort or skill — a worker with
better machines produces more without working harder.

**Equation.**

```
labour productivity = value added / labour input
```

This project uses **value added per person engaged**, measured in millions of yen
(百万円) per person per year.

**Worked example [real].** Aichi, 2019:

```
value added   = 12,810,137 百万円
persons       =    848,565
productivity  = 12,810,137 / 848,565 = 15.10 百万円 per person
```

Roughly 15.1 million yen, about USD 100,000, of value added per worker per year.

**Where used.** The dependent variable of the whole project. Computed in
`src/build_panel.py` as `va_per_worker`; chosen and justified in
`docs/measurement-framework.md`.

**Pitfall.** The ideal denominator is *hours worked*, not persons, because a region
with many part-timers looks artificially unproductive per person. Japan's Census of
Manufacture does not publish hours by prefecture and industry, so persons is the
practical choice. This is a stated limitation, not an oversight.

---

## 1.2 Value added vs gross output

**What it is.** Two different ways to measure what a factory produces.

- **Gross output** (here, 製造品出荷額等, shipment value) is everything the factory
  ships, including the value of materials it bought in.
- **Value added** is gross output *minus* the bought-in materials and energy. It is
  the value the factory itself created.

**Equation (simplified).**

```
value added = gross output − intermediate inputs
```

**Worked example 1 [illustrative].** Two factories each ship ¥100m of product.

| | Factory A | Factory B |
|---|---|---|
| Ships | ¥100m | ¥100m |
| Buys in materials | ¥80m | ¥30m |
| **Value added** | **¥20m** | **¥70m** |

On gross output they look identical. On value added, B creates three and a half
times as much. A is essentially an assembler; B does the substantive work.

### Why the subtraction is the *right* one: double counting

The deeper reason is not fairness between factories, it is arithmetic. Follow one
piece of steel through a supply chain.

**Worked example 2 [illustrative].** Three firms, one car.

| Stage | Buys in | Sells for | Value added |
|---|---|---|---|
| Miner digs ore | ¥0 | ¥30 | ¥30 |
| Steelmaker makes steel | ¥30 | ¥80 | ¥50 |
| Carmaker makes car | ¥80 | ¥200 | ¥120 |
| **Total** | | **gross output ¥310** | **value added ¥200** |

The economy produced **one ¥200 car**. Value added sums to exactly ¥200. Gross output
sums to ¥310, counting the ore three times and the steel twice. **Only value added
adds up**, which is why GDP is defined as the sum of value added and why a
prefecture-level productivity measure built this way is consistent with how Japan's
Cabinet Office reports manufacturing's contribution to GDP.

### Why it matters for *this* comparison

Now suppose the steelmaker and carmaker merge. Nothing real changes — same ore, same
car, same workers. But gross output falls from ¥310 to ¥230, because the internal
steel sale vanishes. Value added stays at ¥200.

That is **vertical integration bias**, and it is not hypothetical here. A region
whose firms make components in-house records less gross output than an otherwise
identical region that buys them in, for reasons that have nothing to do with
efficiency. The OECD Productivity Manual states it directly: gross-output
productivity changes when the intermediates-to-labour ratio moves for reasons such as
outsourcing, unrelated to technology or efficiency.

Comparing Aichi's vertically integrated automotive keiretsu against import-heavy
clusters on gross output would therefore measure supply-chain structure, not
productivity.

### Where the boundary sits

"Intermediate input" means goods and services consumed in production this period:
materials, fuel, electricity, purchased services. **Labour is not an intermediate
input** — wages are part of value added, which is why value added is what gets
divided among workers and capital. Capital is only partly subtracted, through
depreciation, and only in the net measure (§1.3).

In the source data the subtracted term is 原材料使用額等 (raw materials, fuel and
electricity used), which is why that column is downloaded and preserved alongside
value added even though the analysis never uses it directly.

**Where used.** The core measurement decision, argued in `docs/measurement-framework.md`
§2 and carried through every session. It is why the project compares Aichi's
vertically integrated automotive keiretsu against import-heavy clusters without the
comparison being meaningless.

---

## 1.3 Net vs gross value added, and depreciation

**What it is.** Machines wear out. **Depreciation** is the accounting estimate of
that wearing-out, charged as a cost each year.

- **Gross** value added does not subtract depreciation.
- **Net** value added does.

Net is conceptually cleaner — it is the value genuinely left over after maintaining
the capital stock — but it depends on a depreciation estimate, which is itself a
convention.

**Equation, as Japan's Census of Manufacture defines it.**

Establishments with **30 or more** employees, 付加価値額 (**net**):

```
shipments + inventory change − taxes − materials used − depreciation
```

Establishments with **4 to 29** employees, 粗付加価値額 (**gross**):

```
shipments − taxes − materials used
```

No depreciation, no inventory adjustment.

**Why it matters here.** The published 4+ column is a **blend** of the two, which is
why its label is literally `付加価値額(従業者29人以下は粗付加価値額)` — "value added
(gross value added for establishments with 29 or fewer employees)". The blend ratio
varies by prefecture and **correlates with plant size and capital intensity**, which
are exactly the things the analysis is trying to explain. That is systematic bias,
not random noise.

**Where used.** Documented in `docs/variable-definitions.md` §3. Drove the
choice between table 3-01 (4+, blended) and 3-03 (30+, clean net) — see §4.9.

---

## 1.4 Persons engaged vs employees

**What it is.** 従業者数 counts **persons engaged**, which includes working
proprietors and unpaid family workers, not only paid employees.

**Why it matters.** Translating it as "employees" understates the labour input,
especially in industries full of small owner-managed workshops. It also means the
denominator includes people who receive no wage, so productivity here is not the same
as output per wage-earner.

**Where used.** Flagged throughout; the label is preserved in Japanese in
`docs/variable-definitions.md` precisely so it is not silently redefined.
It also explains the 2016 definitional break — see §4.3.

---

## 1.5 Nominal vs real, and a limitation of this project

**What it is.** A **nominal** figure is in the prices of its own year. A **real**
figure has been adjusted so that price changes are removed and only volume changes
remain, using a price index called a **deflator**.

**Equation.**

```
real value added (year t, base year b) = nominal value added_t × (deflator_b / deflator_t)
```

**Worked example [illustrative].** A factory's value added rises from ¥100m to ¥105m
while output prices rise 5%. Nominal growth is +5%. Real growth is **zero** — it is
producing the same volume, sold at higher prices.

**Where used — and the gap.** **This project has not deflated anything. All value
added is nominal.**

What that does and does not affect:

- **Cross-sectional comparisons are unaffected.** Within a single year every
  prefecture faces broadly the same price level, so rankings, the location quotient,
  the shift-share decomposition and the 6.62× within-industry spread all stand.
- **The growth figure is affected.** The headline "+0.34% a year, 2016–2019" is
  **nominal** growth. Real productivity growth could be lower or negative depending
  on manufacturing output prices over that window.

The honest statement is: nominal value added per worker was roughly flat. Calling it
"productivity growth" without the qualifier overstates what was measured. Correcting
this would need an industry-level output deflator, which is a separate acquisition.

---

## 1.6 SNA 2008 and the OECD productivity manual

**What they are.** The **System of National Accounts 2008** is the international
standard for how countries measure their economies; §19.47 defines labour
productivity as value added per unit of labour input. The **OECD *Measuring
Productivity*** manual is the practical companion.

**Why it matters.** Following them means this project's numbers are comparable with
official statistics and defensible to anyone who knows the field, rather than being
a bespoke index invented for the occasion.

**Where used.** The justification for choosing value added per worker, with citations,
in `docs/measurement-framework.md` §2 and its source list.

---

# 2. Regional and agglomeration economics

## 2.1 Agglomeration economies

**What it is.** The idea that firms become more productive by locating near other
firms in the same or related industries. Alfred Marshall (1890) gave three
mechanisms, still the standard framing:

1. **Labour market pooling** — a thick local pool of workers with the right skills,
   so firms fill vacancies faster and workers find jobs faster.
2. **Input sharing** — specialised suppliers can exist because local demand is large
   enough to support them.
3. **Knowledge spillovers** — techniques and know-how move between firms through
   people talking, moving jobs, and observing each other.

**Where used.** The theoretical motivation for **H1**, that specialization raises
productivity. Stated in `docs/measurement-framework.md` §4, tested indirectly in
Session 03 and properly framed in Session 04.

**Pitfall.** Agglomeration predicts that being *concentrated in an industry* raises
productivity *in that industry*. It does not predict that concentrated regions have
high overall productivity, because a region concentrated in a low-value industry will
still look unproductive. Conflating the two is what made the early tests
uninformative — see §3.13.

---

## 2.2 Location quotient (LQ)

**What it is.** A measure of how concentrated a region is in an industry, relative to
the country as a whole. LQ = 1 means the region has exactly the national share.
LQ = 2 means twice the national share.

**Equation, as implemented in `src/build_panel.py`.**

```
                employment in industry i in prefecture p   ⁄   all manufacturing employment in p
LQ(p, i)  =  ─────────────────────────────────────────────────────────────────────────────────
                employment in industry i nationally        ⁄   all manufacturing employment nationally
```

Equivalently, the region's share of that industry divided by the nation's share.

**Worked example [real].** Aichi, transport equipment, 2019:

```
Aichi transport employment      =   317,202
Aichi all manufacturing         =   848,565
National transport employment   = 1,064,560
National all manufacturing      = 7,717,646

Aichi share    = 317,202 / 848,565     = 0.3738   (37.38%)
National share = 1,064,560 / 7,717,646 = 0.1379   (13.79%)

LQ = 0.3738 / 0.1379 = 2.71
```

Transport equipment is 37% of Aichi's manufacturing employment against 14%
nationally, so Aichi is **2.71 times as concentrated** in car-making as Japan
overall. That single number is the quantitative form of "Aichi is Toyota country."

**Where used.** Computed in `src/build_panel.py` (`lq`, `lq_top`, `lq_max`), stability
tested in `src/lq_break_test.py`, used as the specialization measure for H1.

**Pitfall.** Three distinct ways the location quotient misleads, and this project hit
the first two.

**1. LQ is blind to which industry.** Two prefectures with LQ = 3 in chemicals and in
leather score identically and have wildly different productivity — chemicals runs at
30.2 million yen per worker nationally, leather at 5.9. This is the confound Session
04 identified, and it is why the prefecture-level specialization tests were
uninformative (§3.12).

**2. LQ is a ratio of shares, so a tiny base can produce a spectacular score.** The
denominator is a national share, which for a small industry is small, so a single
mid-sized plant can dominate a prefecture's ratio. Real cases from 2019:

| Prefecture | Industry | LQ | Employment |
|---|---|---|---|
| Wakayama | Petroleum & coal | **5.41** | 1,013 |
| Yamagata | Leather | 4.02 | 998 |
| Akita | Leather | 3.18 | 496 |
| *Aichi* | *Transport equipment* | *2.71* | *317,202* |

Wakayama's petroleum LQ is **twice Aichi's transport-equipment LQ**, on one three-
hundredth of the workforce. Read naively, that says Wakayama is Japan's most
specialized manufacturing region. It is an artefact of one refinery. Any LQ-based
claim needs the underlying headcount beside it.

**3. LQ depends on how finely industries are classified.** A region spread evenly
across five kinds of machinery looks diversified at 2-digit level and highly
specialized at 4-digit level. The same region, the same plants, a different number.
This project uses 24 two-digit divisions throughout, so LQs here are not comparable
with LQs computed on a finer classification.

---

## 2.3 Herfindahl–Hirschman Index (HHI)

**What it is.** A measure of how concentrated a whole distribution is, originally
built for market concentration. Here it measures how concentrated a prefecture's
manufacturing employment is across the 24 industries. Higher means less diversified.

**Equation, as implemented in `src/build_panel.py`.**

```
HHI(p) = Σ over industries i of  s(p,i)²

where s(p,i) = industry i's share of prefecture p's manufacturing employment
```

Bounds: if employment is spread evenly across all 24 industries,
HHI = 24 × (1/24)² = 1/24 ≈ 0.042. If everything is in one industry, HHI = 1.

A useful reading is **1/HHI = the effective number of industries** — how many
equally-sized industries the region behaves as though it has.

**Worked example [real].** 2019:

| Prefecture | HHI | Effective industries (1/HHI) |
|---|---|---|
| Fukushima | 0.0598 | 16.7 — the most diversified |
| Tokyo | 0.0817 | 12.2 |
| Aichi | 0.1720 | 5.8 |
| Okinawa | 0.2445 | 4.1 — the most concentrated |

Even Okinawa, the most concentrated prefecture in Japan, behaves like it has four
industries. **No Japanese prefecture is a one-industry region.** That fact turns out
to drive the central result of Session 04 — see §3.12.

**Where used.** `src/build_panel.py` as `hhi_employment`; the diversity measure for
H3 (retired). The Herfindahl index itself remains in the panel as `hhi_employment`.

---

## 2.4 Specialization vs diversification: MAR and Jacobs

**What it is.** Two opposed theories about what makes regions productive.

- **MAR externalities** (Marshall–Arrow–Romer): specialization wins. Concentrating in
  one industry deepens expertise and supplier networks.
- **Jacobs externalities** (Jane Jacobs): diversity wins. Innovation comes from
  unrelated industries colliding, and diversified regions absorb shocks better.

**Where used.** The two are in deliberate tension in this project's hypotheses.
**H1** is a MAR claim (specialization raises the *level* of productivity). **H3** is a
Jacobs claim (diversification raises *stability*). `docs/measurement-framework.md` §4
notes explicitly that both may hold at once, because specialization can raise the
level and the volatility simultaneously.

---

## 2.5 Shift-share analysis

**What it is.** A technique for splitting a region's performance gap into "what it
does" versus "how well it does it." It is the analytical core of Session 04.

**The question it answers.** Yamaguchi is far more productive than the national
average. Is that because Yamaguchi happens to host chemicals, an inherently
high-value industry? Or because Yamaguchi's chemical plants outperform chemical
plants elsewhere?

**Equation, as implemented in `src/shift_share.py`.**

```
mix    = Σ ( s_pi − s_Ni ) × π_Ni        industry composition, valued at national rates
within = Σ   s_pi × ( π_pi − π_Ni )      performance inside each industry
gap    = mix + within                    exactly

s_pi = industry i's share of prefecture p's employment
s_Ni = industry i's share of national employment
π_pi = productivity of industry i in prefecture p
π_Ni = productivity of industry i nationally
```

Reading the two terms:

- **mix > 0** — the prefecture is weighted toward industries that pay well nationally.
- **within > 0** — the prefecture beats the national rate inside the industries it has.

**Worked example [real].** Aichi, 2019:

```
Aichi productivity      = 15.0962
national benchmark      = 12.9917
gap                     = +2.1045

    mix     = +0.4173     from holding transport equipment
    within  = +1.6873     from beating national rates inside its industries
    ----------------------
    sum     = +2.1046     ✓  (residual −8.9e-16)
```

**Only 20% of Aichi's advantage comes from being in car-making. 80% comes from Aichi
being better at it than everywhere else.** Aichi is not productive because cars are
lucrative; it is productive because Aichi is unusually good at making them.

**Where used.** `src/shift_share.py`, Chart 6, Session 04 Finding 3.

**Pitfall — and the bug this project hit.** The identity `gap = mix + within` only
holds if the gap is measured against **the same benchmark the decomposition uses**.
An early version measured the gap against *global* national productivity while
decomposing over each prefecture's surviving industry subset — two different
benchmarks, silently subtracted — and left a residual of 1.37 against gaps of order
1 to 7. The numbers looked plausible and were wrong. `decompose()` now returns the
benchmark explicitly and asserts the identity per prefecture, achieving 4e-15.

### Does that bug damage the project's credibility?

The honest answer has two halves that point opposite ways.

**The bug itself: no, and arguably the reverse.** It was caught during planning,
before any result was computed for publication. It never reached a finding, a chart
or a document. Every shipped Session 04 number comes from the corrected module, whose
identity assertion runs on all 47 prefectures in all four years and passes at
~4e-15. The failure mode it guarded against — plausible numbers that do not add up —
is now impossible to ship silently.

There is a second-order detail that is more interesting than the bug. **My first
diagnosis of the cause was also wrong.** I attributed it to national shares not
summing to 1 after reindexing. Expanding the two terms shows the identity holds
regardless of what those shares sum to; the real cause was the mismatched benchmark.
That wrong diagnosis was caught by writing a regression test that *failed to fail* —
the test built on the wrong theory passed when it should have caught the bug. A
plausible explanation is not a verified one.

**The real limitation: yes, and it is a genuine one — specification dependence.**
Shift-share has no single canonical form. The shipped two-way decomposition gives
`within` the prefecture's own weights, which folds the interaction between
composition and performance into the within term. A three-way form separates it:

| Specification | sd(mix) | sd(within) | sd(interaction) | ratio | within-dominant |
|---|---|---|---|---|---|
| Two-way (shipped) | 0.867 | 2.215 | — | 2.56 | 37 / 47 |
| Three-way | 0.867 | 2.259 | **1.189** | 2.61 | 38 / 47 |

**The headline conclusion is robust** — within-industry performance dominates
industry mix under either form. But the interaction term carries about **28%** of the
total variation, and the two-way form attributes all of it to "within". That
overstates *pure* within-industry performance for the most specialized prefectures:

| Prefecture | Two-way within | Three-way within | Interaction |
|---|---|---|---|
| Yamaguchi | +4.97 | **+1.26** | **+3.71** |
| Aichi | +1.69 | +1.04 | +0.65 |
| Tokyo | −0.71 | −0.96 | +0.25 |

So the correct reading of Aichi is **roughly half within-industry performance, a
third interaction, a fifth industry mix** — not "80% from being good at it". And
Yamaguchi's advantage is mostly *interaction*: it is both concentrated in chemicals
and unusually good at chemicals, and the two reinforce. That is a more interesting
finding than either term alone, and the two-way form hides it.

**Net assessment.** The bug is a non-issue for credibility because it was caught by
design rather than luck. The specification dependence is a real limitation, it is now
quantified rather than assumed, and the headline survives it.

---

## 2.6 Structural change

**What it is.** Shifts in the composition of an economy — labour moving between
industries — as distinct from changes in productivity within industries.

**Where used.** The `mix_effect` column *is* the structural component. Session 04's
finding that mix effects are small (sd 0.87 against 2.22 for within) says Japanese
prefectures differ less in structure than in execution.

---

## 2.7 Convergence

**What it is.** The idea that places starting from a lower base grow faster, because
catching up is easier than pushing the frontier. Formally, **β-convergence** is a
negative relationship between initial level and subsequent growth rate.

**Equation.** The test is a regression of growth on the starting level:

```
growth_p = α + β · log(productivity_p, initial) + ε_p       β < 0 means convergence
```

Logs are used so β reads as "a 1% higher starting level is associated with β
percentage points less growth", independent of scale.

**Status in this project: tested, then withdrawn.** Convergence was estimated on the
2016–2019 panel and produced a negative coefficient of the expected sign. The result
is **not reported here**, because it was one of 15 tests run at n = 47 with no
correction for multiple comparisons, and none of those survived correction. The
analysis notebook has been removed along with the other hypothesis-testing work.

**Why it still belongs in this document.** Convergence is a confounder for any future
hypothesis about regional growth, not just the retired one. Whenever growth is
regressed on a regional characteristic, initial level belongs on the right-hand side,
because places starting lower tend to grow faster for reasons unrelated to the
characteristic being tested. It is also **entangled with demographics** — aged
prefectures tend to start from lower productivity — so the two compete for the same
variation and neither can be cleanly attributed at this sample size.

**Practical implication for new hypotheses.** A growth specification at n = 47 that
needs to separate two correlated regressors is unlikely to succeed. Designs that
compare *levels* within industries, where the sample is 1,128 rather than 47, avoid
the problem entirely.

---

## 2.8 Capital deepening

**What it is.** Raising the amount of capital (machines, automation) per worker. It
raises output per worker without anyone working harder.

**Equation.**

```
capital per worker = tangible fixed assets, year-end stock / persons engaged
capital deepening  = the growth rate of that ratio
```

**The hypothesis, as a chain.** If labour scarcity drives automation which drives
productivity, then **both** links must hold:

```
aging  ->  capital deepening  ->  productivity growth
```

A chain is only as strong as its weakest link, so testing the links separately is
more informative than testing the hypothesis as a whole.

**Data.** Capital stock is published: Census of Manufacture table 3-04
(有形固定資産額, prefecture × industry). It covers **establishments with 30+
employees only**, so every measure in this test is built on the 30+ basis, pairing
table 3-04 capital with table 3-03 productivity. Dividing 30+ capital by 4+
employment would be meaningless.

**Descriptive magnitude [real].** National capital per worker on the 30+ basis rose
from **11.88 to 12.60 million yen** between 2016 and 2019, roughly +2.0% a year. That
is a level fact from the published totals, not a test result, and it stands.

**Status in this project: tested as a hypothesis, then withdrawn.** Capital deepening
was the candidate explanation for the retired H2, tested as a two-link chain — aging
drives automation, automation drives productivity. Those correlations are **not
reported here**, for the same reason as §2.7: 15 tests at n = 47 with no correction,
none surviving it. The analysis notebook has been removed.

**The data survives and is validated.** `processed_data/manufacturing_{2016..2019}_table3-04.csv`,
1,128 rows each, capital mapped as `capital_stock_year_end`. Any new hypothesis
involving capital intensity can use it immediately without re-acquisition.

**Two constraints to design around.**

*Coverage.* Table 3-04 exists only for **30+ employees**, while the main panel is 4+.
Capital must be paired with table 3-03 productivity so numerator and denominator share
coverage. Results on that basis describe **large-establishment** behaviour, which is a
different quantity from the main panel rather than a smaller sample of it.

*Label drift.* The same measures are spelled `有形固定資産額[年末現在高]` in the 2017–2018
surveys and `有形固定資産額[(A+B-E-F) 年末現在高]` from 2019. Identical quantities,
different strings; left unmapped this silently returns **zero rows** rather than
raising. Both spellings are in `MEASURE_MAP`.

**Pitfall.** Capital stock here is a **nominal book value** net of accumulated
depreciation, not a constant-price capital stock. It reflects acquisition prices and
accounting depreciation schedules, so comparing it across regions with different
vintages of plant is rougher than the clean ratio suggests. See also §1.5.

---

## 2.9 Demographic aging

**What it is.** The share of population aged 65 and over. A high aging ratio means a
shrinking working-age base.

**Equation, as implemented in `src/build_panel.py`.**

```
aging_ratio       = population 65+ / total population
working_age_share = population 15–64 / total population
```

**Worked example [real].** 2019 range across Japan: Okinawa 22.1% at the young end,
Akita 36.8% at the old end. More than one in three Akita residents is over 65.

**Where used.** The independent variable for **H2**. Joined into the panel from the
intercensal adjusted population series.

---

## 2.10 Manufacturing intensity

**What it is.** How manufacturing-heavy a regional economy is.

**Equation, as implemented.**

```
mfg_intensity = manufacturing employment / working-age population (15–64)
```

**Worked example [real].** 2019: Aichi 18.2%, Tokyo 2.7%. Nearly one in five
working-age people in Aichi is in manufacturing, against one in 37 in Tokyo.

**Where used.** `src/build_panel.py`. Note the denominator choice: the obvious one
would be total prefectural employment from the Labour Force Survey, but those are
**model-based estimates** published as reference values with large prefecture-level
sampling error. Using working-age population instead removed a noisy dependency
entirely — a deliberate trade of a slightly less natural denominator for a much
cleaner one.

---

# 3. Statistics and inference

## 3.1 Panel data

**What it is.** Data with two dimensions: many units observed over multiple periods.
It supports questions neither a single snapshot nor a single time series can answer,
because you can compare units *and* watch them change.

**Where used.** This project has **two** panels, and keeping them straight is the
central architectural decision:

| Panel | Shape | Rows | Purpose |
|---|---|---|---|
| Prefecture × year | 47 × 4 | **188** | the analysis table |
| Prefecture × industry × year | 47 × 24 × 4 | **4,512** | computing LQ and HHI, and the Session 04 analysis |

`processed_data/panel_prefecture_year.csv` and the four
`manufacturing_<year>_table3-01.csv` files respectively.

---

## 3.2 Cross-section vs time series

**What it is.** A **cross-section** compares many units at one moment. A **time
series** follows one unit over time. A panel does both.

**Where used.** Most findings here are cross-sectional (47 prefectures in 2019),
which is why they support statements about *differences* and not about *causes*. The
only time-series statement is the national trend, and with four observations it can
support a direction and little else.

---

## 3.3 Correlation: Pearson vs Spearman

**What it is.** A number from −1 to +1 summarising how two variables move together.

- **Pearson** measures *linear* association, using the values themselves.
- **Spearman** measures *monotonic* association, using only the ranks. It is
  resistant to outliers and does not assume a straight line.

**Equation.**

```
Pearson  r = covariance(x, y) / ( sd(x) × sd(y) )
Spearman ρ = the Pearson correlation of rank(x) and rank(y)
```

**Worked example [illustrative].** For x = 1, 2, 3, 4 and y = 1, 4, 9, 16 (a perfect
squared relationship): Spearman ρ = **1.0** exactly, because ranks match perfectly.
Pearson r ≈ 0.98, because the relationship is curved, not straight. Neither is
"wrong" — they answer different questions.

**Where used.** Both are reported side by side throughout Session 03, e.g. aging
against growth gives Pearson +0.274 and Spearman +0.327. When they disagree
materially, that is itself information about outliers or non-linearity.

---

## 3.4 Rank correlation as a structural-break test

**What it is.** A specific, cheap use of Spearman: if a definition changes partway
through a data series, do the *rankings* survive?

**Why it works here.** The location quotient is a ratio of shares. A definitional
change that scales every cell by the same factor cancels out entirely in a ratio. The
cancellation is imperfect because the change is not uniform across industries — but
if rank correlation across the break is very high, the ordering is usable.

**Worked example [real].** `src/lq_break_test.py` compares LQ in 2014 against 2016,
across the 2016 employment definition change:

```
pooled Spearman ρ      = 0.9869
per-industry median ρ  = 0.9825
industries above 0.95  = 22 of 24
industries below 0.90  = 0 of 24
```

**Verdict: the LQ ordering survives the break**, so H1 can use eight observations
rather than four. The two weakest industries are "other manufacturing" (0.946) and
leather (0.947), both small and full of owner-managed establishments — exactly where
the definitional change (adding paid company officers) bites hardest. The mechanism
shows up where theory predicts.

**Pitfall.** This tests **ordering**, not levels. It does not license pooling LQ
*levels* across the break without a block dummy.

---

## 3.5 p-values

**What it is.** The probability of seeing an association at least this strong if
there were truly no relationship at all. Small p means "unlikely to be pure chance."

**What it is not.** It is not the probability the hypothesis is true, not a measure of
effect size, and not a licence to claim causation. With n = 47 a correlation needs to
be roughly |r| > 0.29 to reach p < 0.05.

**Worked example [real], and a cautionary one.** The Herfindahl index against
productivity gave r = −0.300, p = 0.040 — conventionally significant, and a modest
effect explaining about 9% of the variance. It was reported as a finding.

**It should not have been.** It was one of 15 tests run across three hypotheses, and
at p = 0.040 it does not survive any correction for multiple comparisons (§3.5a). It
has since been withdrawn.

**Where used.** Reported alongside every correlation in Sessions 03 and 04. All such
findings were **withdrawn in Session 07**; the project now reports magnitudes rather
than significance tests.

---

## 3.5a Multiple comparisons — the error that ended this project's first phase

**What it is.** A p-value threshold of 0.05 means a 5% chance of a false positive **per
test**. Run many tests and false positives become likely rather than rare. Testing is
cheap; the appearance of significance is not evidence.

**Equation.** For *m* independent tests, the chance of at least one false positive is

```
P(at least one) = 1 − (1 − α)^m        α = 0.05, m = 15  ->  54%
```

Two standard corrections:

```
Bonferroni:            reject only if  p < α / m          strict, controls any false positive
Benjamini-Hochberg:    rank p ascending, reject while  p(i) < (i/m)·α    controls the false discovery rate
```

**Worked example [real].** This project ran **15 tests** across its three hypotheses,
all at n = 47, with no correction. Seven reached nominal significance at 0.05.

| | Count |
|---|---|
| Tests run | 15 |
| Nominally significant at 0.05 | **7** |
| Surviving Bonferroni (p < 0.0033) | **0** |
| Surviving Benjamini-Hochberg at q < 0.05 | **0** |
| Expected false positives by chance alone | ~0.75 |

The smallest p-value in the entire project was 0.0129, against a Bonferroni threshold
of 0.0033. The three headline results fared as follows:

| Finding | Raw p | BH q |
|---|---|---|
| aging → growth (30+) | 0.0129 | 0.193 |
| convergence | 0.0342 | 0.103 |
| concentration → productivity | 0.0404 | 0.101 |

**Where used.** Discovered in Session 07 and it ended the project's hypothesis-testing
phase. All three hypotheses were retired and the dependent analysis deleted, rather
than published with caveats.

**Honest framing of the correction itself.** Bonferroni is arguably too strict here:
these are not 15 independent tests of one family, but several correlated probes of
three hypotheses stated before the data was seen. A purist would also note that the
number of tests is itself a judgement — should the two coverage bases count once or
twice? That ambiguity is precisely the **garden of forking paths** problem, and it is
why the count cannot be argued down to a comfortable number.

The defensible conclusion is not "every finding was noise" but "**no single result was
individually robust**, so none should carry a headline."

**What survives this critique.** Quantities that do not depend on a significance
threshold: exact decompositions, variance shares, dispersion ratios, and reconciliation
checks. Those are what the project reports now.

**Pitfall.** The correction is not a ritual to perform at the end. It changes what you
should *design*: at n = 47, a study that needs several tests to make its case cannot
make it. Moving to the prefecture × industry panel raises the sample from 47 to 1,128
and is the structural fix, not a statistical patch.

---

## 3.6 Compound annual growth rate (CAGR)

**What it is.** The single constant growth rate that would take you from the starting
value to the ending value over the period. It is a **geometric** mean, which is the
correct average for things that compound.

**Equation.**

```
CAGR = (ending / beginning)^(1 / number of periods) − 1
```

**Worked example [real].** National value added per worker, 2016 to 2019 — three
growth periods:

```
CAGR = (12.9877 / 12.8565)^(1/3) − 1 = +0.3390%
```

The arithmetic mean of the three annual rates gives +0.3880% instead. The arithmetic
mean **overstates**, because it ignores compounding and is pulled up by volatile
intermediate years. This gap is small here and can be large for volatile series.

**Where used.** The headline national trend figure, Chart 4, and the per-prefecture
growth rates used to test H2. See §1.5 — this is *nominal* growth.

---

## 3.7 Logarithms in productivity analysis

**What it is.** Taking logs turns multiplicative relationships into additive ones and
makes distributions more symmetric. A difference of 0.1 in logs is approximately a
10% difference in levels.

**Why it is used here.** Productivity is right-skewed: most prefecture-industry cells
sit near 10 million yen per worker, a few reach 35 and beyond. Raw values let those
few dominate any variance calculation. Logs put proportional differences on an equal
footing, which is what "how different are these places?" actually means.

**Where used.** `variance_shares()` in `src/shift_share.py` operates on
`log(value_added / employment)`. Chart 7 uses a log x-axis for the same reason —
within-industry spreads reach 38×, and a linear axis crushed the lower two-thirds.

**Pitfall.** Logs are undefined for zero and negative values. Two cells in 2019 have
negative value added (see §5.5), and they are explicitly dropped from log-based
measures and retained where levels are valid.

---

## 3.8 Weighted vs unweighted means

**What it is.** An unweighted mean treats every observation equally. A weighted mean
lets larger observations count more.

**Worked example [illustrative].** Two prefectures: one with 1,000,000 workers at 10
million yen each, one with 1,000 workers at 20 million yen each.

```
unweighted mean of the two rates = (10 + 20) / 2 = 15.0
employment-weighted (true national) = (1,000,000×10 + 1,000×20) / 1,001,000 = 10.01
```

The unweighted figure of 15.0 describes no one. The tiny prefecture gets equal billing
with one a thousand times its size.

**Where used.** The national trend in Chart 4 is computed as total value added divided
by total employment, **not** as the mean of 47 prefecture ratios, so large prefectures
carry their true weight. The variance decomposition is employment-weighted for the
same reason.

---

## 3.9 Dispersion: ratios, IQR, standard deviation

**What it is.** Three ways to say "how spread out is this?"

- **Max/min ratio** — intuitive, but driven entirely by two extreme observations.
- **Interquartile range (IQR)** — the middle 50%, robust to outliers.
- **Standard deviation** — the typical distance from the mean, in original units.

**Where used.** All three, deliberately. Max/min ratios for the headline comparisons
(5.90× between industries, 6.62× within). IQR as the box in Chart 7. Standard
deviation to compare the shift-share components (sd(within) = 2.22 against
sd(mix) = 0.87).

**Pitfall.** The headline 5.90× and 6.62× figures are max/min ratios and therefore
outlier-sensitive. Chart 7 shows the full distributions precisely so the reader can
see whether the ratio is representative or driven by one extreme prefecture.

---

## 3.10 Variance decomposition

**What it is.** Splitting the total variation in an outcome into portions attributable
to different groupings. Here: of all the variation in productivity across
prefecture × industry cells, how much is explained by knowing the *industry*, and how
much by knowing the *prefecture*?

**Equation, as implemented in `variance_shares()`.**

```
total sum of squares  TSS = Σ w × ( log_p − grand_mean )²
explained by grouping g   = Σ w × ( group_mean(g) − grand_mean )²
share                     = explained / TSS

w = employment weight
```

**Worked example [real].** 2019, 1,091 cells:

```
industry means alone   explain 51.6% of the variance
prefecture means alone explain 15.0%
```

### Why the two shares do not sum to 100%

This surprises people, so it is worth being concrete. Each share is computed
**separately against the same total**, as two independent one-way decompositions, not
as one two-way partition.

**Worked example [illustrative].** Chemicals in Yamaguchi is highly productive. Why?

- Partly because it is **chemicals** — capital-intensive, high value added everywhere.
- Partly because it is **Yamaguchi** — whatever that region does well.

The one-way industry decomposition credits that cell's deviation to chemicals. The
one-way prefecture decomposition credits the same deviation to Yamaguchi. **The
overlapping portion is counted in both**, so the shares can sum to more than 100% —
or, when the two factors offset each other within cells, to less. Here they sum to
66.6% (51.6 + 15.0), meaning a large share of variation is **within** both groupings:
cell-specific, explained by neither factor alone.

A genuine two-way decomposition would partition cleanly into industry, prefecture,
interaction and residual. That is deliberately not done here, because it is
essentially the fixed-effects model being deferred to the next stage (§3.11). The
one-way shares are reported as what they are: an indication of relative magnitude,
not an exhaustive accounting.

**Two design choices worth naming.**

*Employment-weighted*, so a cell with 300,000 workers counts more than one with 300.
An unweighted decomposition would let tiny prefecture × industry cells drive the
result, which is the §3.8 problem.

*In logs*, so the measure is proportional. Without logs the few cells near 35 million
yen per worker would dominate the sum of squares, and the answer would describe the
extremes rather than the distribution (§3.7).

**Where used.** Session 04, the cell-level half of the answer to "geography or
industry composition?" It points the opposite way to the shift-share, and reconciling
the two is the session's central finding — cell-level versus aggregate-level are
different questions.

---

## 3.11 Fixed effects (planned, not yet run)

**What it is.** A regression technique that absorbs everything constant within a
group, so the estimate uses only variation *within* groups. Including **industry
fixed effects** means "chemicals is capital-intensive" is soaked up by the chemicals
dummy, and the remaining coefficient reflects only variation among prefectures inside
the same industry.

**Planned specification.**

```
log(value added per worker)_pi = β · LQ_pi + industry fixed effects + controls + ε_pi
```

1,128 observations per year instead of 47. β is then interpretable as the
agglomeration effect, purged of industry composition.

**Where used.** Not yet run. Documented as the next step in `README.md` §4 and
justified by Session 04's Finding 2: there is substantial within-industry regional
variation for the location quotient to explain.

---

## 3.12 Confounding and omitted variable bias

**What it is.** A confounder is a third variable that drives both things you are
comparing, creating an association that is not what it appears to be.

**Worked example [real], the central one in this project.** The observed relationship
was: more concentrated prefectures are *less* productive (r = −0.30, since withdrawn
— see §3.5a).

The confounder is **which industry they are concentrated in**. Highly concentrated
prefectures are disproportionately rural and food-dominated. Food manufacturing runs
at about 9.1 million yen per worker against a 13.0 national average. So concentration
was partly acting as a proxy for "rural and food-dominated", and the correlation said
little about agglomeration either way.

Note this defect is **independent of the statistical one**. Even had the correlation
been strongly significant, it would not have measured what it was taken to measure. A
confounded design cannot be rescued by a larger sample.

**Where used.** The core reasoning of Session 04, and the reason the retired H1 is
described as **never tested** rather than tested and rejected. It is also the main
argument for moving to a prefecture × industry design: holding industry constant is
what removes this specific confounder.

---

## 3.13 Aggregation bias — the mistake this project made

**What it is.** Statistics computed on aggregated data behave differently from
statistics on the underlying units. Averaging compresses variation, so a dispersion
measured on aggregates is not comparable with one measured on components.

**The mistake [real].** Session 03 concluded:

> productivity spans 5.90× across industries but only 2.93× across prefectures,
> therefore industry mix matters about twice as much as geography.

This is invalid. The 5.90× is the spread of **industry means**. The 2.93× is the
spread of **prefecture aggregates**, and each prefecture aggregate is an
employment-weighted average over 24 industries. Averaging pulls values toward the
centre, so prefecture aggregates are *mechanically* compressed. Comparing them
against raw industry means compares dispersions at two different levels of
aggregation.

**The correction.** The like-for-like comparison holds industry fixed and asks how
much prefectures differ *within* an industry:

| Comparison | Value |
|---|---|
| Between industries (national means) | 5.90× |
| Within industries, across prefectures (median) | **6.62×** |
| Prefecture aggregates — *not comparable to the above* | 2.93× |

Regional and industry effects turn out to be comparable in size, with regional
slightly **larger** — the opposite conclusion, from the same data, once the
comparison is made at a consistent level.

**Where used.** Documented in `notebooks/02_industry_mix_analysis.ipynb` and Session 04 of
`docs/work-log.md`. This is closely related to the **ecological fallacy**, where
conclusions about individuals are drawn from group-level data.

---

## 3.14 Missing data mechanisms: MCAR, MAR, MNAR

**What it is.** Why data is missing determines what you may do about it.

- **MCAR** (missing completely at random) — missingness is unrelated to anything.
  Dropping is safe.
- **MAR** (missing at random) — missingness depends on observed variables. Can be
  modelled.
- **MNAR** (missing not at random) — missingness depends on the missing value itself.
  Dangerous, and no fix is fully satisfactory.

**Which applies here.** Confidentiality suppression is **MNAR**. A cell is suppressed
*because* it has too few establishments — the value itself determines the
missingness.

**Worked example [real].** 2019, table 3-01: 25 cells suppressed and 10 absent, out
of 1,128. They are concentrated in leather (12), information and communication
equipment (9) and rubber (4) — the thin industries.

**Why zero-filling would be a disaster.** Zero-filling a suppressed cell asserts that
a prefecture has no activity in an industry where it in fact has a small amount. That
would push the location quotient for thin industries toward zero and distort exactly
the small-industry cells the LQ analysis depends on. A systematic, direction-known
bias.

**Where used.** `classify_value()` in `src/validate_manufacturing.py` maps suppression
glyphs to `NaN` with a `suppressed` flag, never zero. Coverage is tracked per row as
`va_coverage_pct`.

---

## 3.15 Structural breaks

**What it is.** A point where the definition or collection method of a series changes,
so values before and after are not comparable even though they sit in one column.

**Where used.** Two in this data:

1. **Reference year 2016** — paid company officers (有給役員) were added to the
   employment count and the survey date moved. Affects employment only, not financial
   items.
2. **Reference year 2020** — the Census of Manufacture was abolished; its successor is
   sample-based and excludes individual proprietorships. Not a continuation.

The response was to test whether the break mattered (§3.4) rather than assume, and to
use a block dummy rather than a calibrated adjustment when it does.

---

## 3.16 Outliers and legitimate extreme values

**What it is.** An extreme value is not automatically an error. The question is
whether it is a mistake or a real observation.

**Worked example [real].** Two cells have **negative** value added in 2019:

```
Wakayama, petroleum & coal products   −26,435 百万円
Ehime,    petroleum & coal products    −4,313 百万円
```

These are genuine. Net value added subtracts depreciation, and an oil refinery has
enormous depreciation. In a bad margin year the subtraction exceeds the operating
surplus. Clipping these to zero would be falsifying data.

**Where used.** `src/validate_manufacturing.py` preserves negatives and reports them
separately rather than coercing them; they are excluded only from log-based measures,
where the log is undefined.

---

# 4. Official statistics and data quality

## 4.1 Census vs sample survey

**What it is.** A **census** attempts to contact every unit. A **sample survey**
contacts some and grosses up to an estimate.

**Where used.** The 工業統計調査 (Census of Manufacture) was a complete enumeration of
establishments with 4+ employees. Its successor from 2022, the 経済構造実態調査
(Economic Structure Survey), is **sample-based** — covering the top 90% of shipment
value per industry class and estimating the rest — and **excludes individual
proprietorships and non-corporate bodies**. Hyogo Prefecture's own guidance states
the two cannot simply be compared.

### Can 2021 onward be analysed separately and compared? No — and not for that reason

The comparability argument above is real but it is **not the binding constraint**.
Checked directly against the API: the Economic Structure Survey's manufacturing
tables (`0004048573`, `0004048574`, `0004048575`) have exactly two dimensions —
measures, and a combined time × industry key. **There is no area dimension at all.**

Prefecture-level Economic Structure Survey output exists only for broad-division
sales (産業大分類別売上金額) and for wholesale and retail. Neither is manufacturing
value added by industry.

So the honest answer is that **manufacturing value added by prefecture is not
published for 2021 onward, at any granularity**. There is nothing to compare, well or
badly. The obstacle is availability, not methodology — a stronger and simpler reason
than the one this section originally gave.

### What *is* possible: reference year 2020

The 2021 Economic Census (令和3年経済センサス-活動調査) is a **complete enumeration**
and does publish by prefecture. It supplies reference year 2020, and it turns out to
be directly compatible.

**The gate [real].** These tables carry the prior year (2019) alongside 2020 as a
comparison, so the two instruments can be checked **on the same year**:

| Measure | Max absolute difference, 2019 | Exact matches |
|---|---|---|
| Employment | **0** | 47 / 47 |
| Value added | **0** | 47 / 47 |
| Establishments | **0** | 47 / 47 |

The Economic Census **reproduces** the Census of Manufacture's 2019 figures rather
than restating them on a different basis. Reference year 2020 therefore sits on the
same measurement basis as 2016–2019 and has been appended to the panel, tagged with
an `instrument` column so the two sources are never silently pooled.

**What 2020 cannot supply.** The Economic Census publishes prefecture × industry
establishments, shipments and value added — but employment only at **prefecture
level**. The location quotient and the Herfindahl index both need prefecture ×
industry employment, so neither can be computed for 2020. Those columns are null
rather than filled with a value-added analogue, which would be a different measure.

**And one caveat about the year itself.** 2020 is the COVID year. National value
added per worker was 12.970 against 12.988 in 2019 — essentially flat, which is
itself notable. But any growth rate spanning 2020 is measuring a shock, not a trend,
which is why notebooks 01 and 02 filter to the Census of Manufacture window and 2020
is reported separately.

**Verification:** `python src/econ_census.py` re-runs the gate.

---

## 4.2 Reference period vs survey date

**What it is.** The **survey date** is when the questionnaire is administered. The
**reference period** is the stretch of time the answers describe. They are often not
the same, and confusing them shifts an entire time axis.

**Where used — the project's first major catch.** From the 2017 survey onward, Japan's
Census of Manufacture moved the survey date from 31 December to 1 June, and financial
items refer to the **previous** calendar year. METI states it directly:

> 平成29年調査より、調査日を12月31日から翌年6月1日に変更 ... 経理事項については
> 平成28年1月～12月の実績を調査しています

So a dataset labelled `2019年確報` contains **2018** value added.

**How it was proven, not assumed.** The 2019 survey's unmarked national row equals the
2020 survey's row explicitly labelled `全国計(2018年)`, to the yen:

```
2019年確報, 全国計 (unmarked)   = 331,809,377 百万円
2020年確報, 全国計(2018年)      = 331,809,377 百万円   ← identical
```

**A second trap.** e-Stat's own `SURVEY_DATE` metadata field reports `201901-201912`
for that dataset and is **wrong for every survey from 2017 onward** — it formulaically
encodes the survey year as a Jan–Dec span.

**Where documented.** `docs/reference-years.md`. Every year in this project
is a **reference year**.

**Pitfall.** One consequence remains baked in: after 2016, value added for year T is
divided by a headcount taken on 1 June of year T+1. The mismatch is identical across
all 47 prefectures, so rankings are unaffected, but it should be stated.

---

## 4.3 Statistical disclosure control

**What it is.** Statistical agencies suppress cells that could identify an individual
business. If one prefecture has two rubber factories, publishing their combined value
added effectively reveals each firm's figures to the other.

**Where used.** e-Stat marks these with `X`, `Ｘ` (full-width) or `χ` (Greek chi), and
nil values with `-`, `***` and several other glyphs. `src/validate_manufacturing.py`
carries explicit glyph sets:

```python
SUPPRESSED_GLYPHS = {"X", "x", "Ｘ", "ｘ", "χ", "Χ", "ｘ"}
NIL_GLYPHS = {"-", "－", "‐", "‑", "–", "—", "―", "ー", "*", "**", "***", ...}
```

**Pitfall.** A regex matching only ASCII `X` silently misses the Greek and full-width
variants. e-Stat also offers a display option that replaces these with `0` — which
must never be used. The distinction between "suppressed" and "genuinely nil" is
preserved as separate flags because they mean different things: one is a hidden
positive value, the other is a real zero.

---

## 4.4 Control totals and reconciliation

**What it is.** Checking that your computed parts sum to an independently published
whole. It is the single most effective validation in official-statistics work,
because it catches filtering, joining and unit errors at once.

**Worked example [real].** Summing 47 prefectures and comparing against the published
national row:

| Measure | Gap |
|---|---|
| Establishments | 0.0000% |
| Employment | 0.0000% |
| Shipments | −0.0239% |
| Value added | −0.0317% |

Counts reconcile **exactly** because counts are never suppressed. The monetary gaps
are small, negative, and track the suppressed-cell count — which is the *expected*
signature of correct suppression handling, since suppressed cells are missing from
the prefecture sum but present in the national total. Had the pipeline zero-filled,
the gap would look similar but the flags would be wrong; had it dropped rows, the row
count would not be 1,128.

**Where used.** `src/validate_manufacturing.py`, reported in every
`metadata/validation_*.json`.

---

## 4.5 Using the published total instead of summing parts

**What it is.** A direct consequence of suppression. The `【00】製造業計` row is the
publisher's own prefecture total, and it **includes** the establishments whose
individual industry cells were suppressed.

**Worked example [real].** 2019 coverage if you sum the 24 industries instead:

| Prefecture | Coverage | Understated by |
|---|---|---|
| Kochi | 98.46% | 1.54% |
| Nagasaki | 98.93% | 1.07% |
| Okinawa | 99.32% | 0.68% |
| Aichi | 100.00% | 0.00% |

Nationally this recovers 28,992 百万円. Small in absolute terms — but **the error is
concentrated in small prefectures**, the ones at the bottom of the productivity
distribution. Summing would have systematically tilted any regression of productivity
on size or specialization.

**Where used.** `load_prefecture_totals()` in `src/build_panel.py` reads the `【00】`
row from raw JSON for totals, while industry shares for LQ and HHI come from the 24
industry rows, where shares must sum to 1.

---

## 4.6 Industrial classification (JSIC)

**What it is.** The Japan Standard Industrial Classification, the official scheme for
sorting establishments into industries. This project uses the **2-digit divisions**,
codes 09 through 32, giving 24 manufacturing industries.

**Where used.** Throughout. Codes 25, 26 and 27 (general, production and business
machinery) confirm the post-2008 JSIC structure, which means the major manufacturing
reclassification predates the 2010 analysis window — so no reclassification break sits
inside the data. Finer 4-digit detail exists but was cut from scope: 24 industries is
ample for LQ and HHI, and finer cells suffer far more suppression.

---

## 4.7 Double counting in geographic hierarchies

**What it is.** Official geography tables often mix levels — prefectures alongside
cities that sit *inside* those prefectures.

**Where used.** The e-Stat geography dimension has **73 items, not 47**: the 47
prefectures, 21 designated cities that are subsets of them (Nagoya inside Aichi,
Yokohama inside Kanagawa), and five national rows, four of which carry other years'
data for comparison.

Summing all 73 would double-count roughly the entire urban population of Japan.
`src/validate_manufacturing.py` handles this by **whitelisting** the 47 prefecture
names rather than blacklisting the cities — a whitelist fails loudly if the source
changes, a blacklist fails silently.

Prefecture names also appear without their 都/府/県 suffix, and `東京` and
`東京特別区` are separate items where the latter is a subset of the former.

---

## 4.8 Intercensal estimation

**What it is.** A full census happens every five years. Between them, agencies publish
estimates. Two kinds exist, and the difference matters:

- **Projected estimates** — roll forward from the last census.
- **Intercensal adjusted estimates** (国勢調査結果による補間補正人口) — computed after
  the *next* census, reconciled against both endpoints.

**Where used.** Population comes from the intercensal series (statsDataId
`0004021110`), chosen deliberately over the projected estimates because the analysis
window 2016–2019 sits **between** the 2015 and 2020 censuses, so the intercensal
figures are benchmarked at both ends rather than extrapolated from one.

---

## 4.9 Units, and a bug they caused

**What it is.** Official statistics publish in domain-conventional units that are
rarely the base unit.

**Where used.** Two in this project:

- Monetary values are in **百万円** (millions of yen) — not yen, not thousands.
- Population is in **千人** (thousands of persons).

**The bug [real].** The population figures were joined without conversion, making
`mfg_intensity` wrong by a factor of 1,000 — Aichi read 181.59 instead of 0.182. It
was caught because Tokyo's population showed as 14,007.

The fix converts to persons **and asserts the unit is 千人**, so a future vintage
published in different units fails loudly instead of silently rescaling.

**Pitfall.** Verify units from the source, never by inference. Here the `@unit` field
on every cell said `千人`, and the national row read 127,042 against Japan's known
127.0 million — two independent confirmations.

---

# 5. Manufacturing domain knowledge

## 5.1 Establishment vs enterprise

**What it is.** An **establishment** is a single physical site — one factory. An
**enterprise** is the company that owns it, possibly with many establishments.

**Where used.** The Census of Manufacture counts **establishments**, which is the
right unit for regional analysis: a Toyota plant in Aichi should count as Aichi
activity regardless of where Toyota is headquartered. Using enterprises would
attribute output to head-office locations and badly distort regional figures.

---

## 5.2 Size thresholds

**What it is.** The survey covers establishments with **4 or more** employees.
Smaller workshops are excluded, so the data is not the whole of manufacturing.

**Where used.** Table 3-01 covers 4+; table 3-03 covers 30+ only. The project uses
**3-01 as primary and 3-03 as a robustness check**, a decision reversed from the
original plan. 3-03 gives a cleaner net value added (§1.3) but suppresses roughly
9% of value-added cells against 2.5% for 3-01, and that suppression concentrates in
exactly the thin cells a location quotient depends on (§3.14). The blend bias in
3-01 affects levels, is stable year to year, and is absorbed by prefecture fixed
effects.

Note that 3-03 results measure **large-establishment productivity** — a different
quantity, not merely a smaller sample. Full reasoning in
`docs/variable-definitions.md` §1 and §3.

---

## 5.3 Process vs assembly industries, and capital intensity

**What it is.** **Process** industries (chemicals, petroleum refining, steel) run
continuous plants with enormous machinery and few workers. **Assembly** industries
(furniture, leather, food) are labour-intensive.

**Why it drives the results.** Capital intensity is the main reason productivity
varies across industries. A refinery's output per worker is high because each worker
supervises a vast amount of capital, not because refinery workers are better.

**Worked example [real].** 2019 national value added per worker:

| Industry | 百万円/worker |
|---|---|
| Petroleum & coal | 34.8 |
| Chemicals | 30.2 |
| Beverages & tobacco | 26.9 |
| *national average* | *13.0* |
| Furniture | 8.2 |
| Textiles | 6.1 |
| Leather | 5.9 |

**Where used.** Chart 5, and the explanation for why prefecture-level specialization
measures are confounded (§3.12).

---

## 5.4 The Aichi automotive cluster and keiretsu

**What it is.** **Keiretsu** are the tightly linked supplier networks around Japanese
manufacturers — in Aichi's case, Toyota and the suppliers clustered around it. They
are vertically integrated by relationship rather than by ownership.

**Where used.** The motivating case for the whole project, and the reason value added
was chosen over gross output (§1.2): a vertically integrated cluster records its
supply chain differently from one that imports components, and gross output would
have made the comparison meaningless.

The decomposition then produced the project's most interesting single result: Aichi's
productivity advantage is **80% within-industry execution, 20% industry mix**.

---

## 5.5 Why refining posts negative value added

Covered in §3.16. Net value added deducts depreciation; refineries carry enormous
depreciation; in a weak-margin year the deduction can exceed the operating surplus.
The negative figure is accurate, not an error.

---

# 6. Visualization

## 6.1 Colour-vision deficiency and ΔE separation

**What it is.** Roughly 8% of men have some form of colour-vision deficiency. Two
colours that look distinct to most readers can be identical to them. **ΔE** measures
perceptual distance between colours; simulating deutan/protan/tritan vision and
measuring ΔE tests a palette rather than guessing at it.

**Where used.** The project's two series colours were validated, not eyeballed:

```
blue #2a78d6 vs orange #eb6834
  CVD ΔE 24.7 (protan), 32.7 (tritan)   target ≥ 8
  normal-vision ΔE 33.6                 floor ≥ 15
  contrast vs surface: both ≥ 3:1
```

A third colour (aqua `#1baf7a`) passed separation but sat at 2.74:1 contrast and was
**dropped** rather than accepted with a mitigation. Palette in `src/viz_style.py`.

---

## 6.2 Categorical, sequential and diverging colour

**What it is.** Three colour jobs. **Categorical** encodes identity (unordered
things), **sequential** encodes magnitude (one hue, light to dark), **diverging**
encodes polarity around a meaningful midpoint (two opposed hues, neutral centre).

**Where used.** All charts use a categorical pair with a fixed meaning held across
the project: **blue = the data, orange = the subject of the chart's question, grey =
de-emphasised context**. Consistency across seven charts means a reader learns the
code once.

**Pitfall.** Colouring bars darker-where-bigger on unordered categories double-encodes
length as hue and wastes the only free channel. Avoided throughout.

---

## 6.3 Log scales

Covered in §3.7. Chart 7 uses a log x-axis because within-industry spreads reach 38×
and a linear axis compressed the lower two-thirds into unreadability.

---

## 6.4 Zero baselines and truncated axes

**What it is.** Starting a value axis above zero exaggerates differences. Starting at
zero shows true proportions but can waste space.

**Where used.** Chart 4 (the national trend) uses a **zero baseline deliberately**.
The question is whether productivity is stagnant, and a truncated axis would have
turned a 1% total movement into a dramatic-looking climb. The chart looks empty, and
that emptiness *is* the finding.

---

## 6.5 Boxplots and the IQR

**What it is.** A boxplot summarises a distribution: the box spans the 25th to 75th
percentile (the **interquartile range**), the line inside is the median, whiskers
reach most of the rest, and individual points are outliers.

**Where used.** Chart 7 shows 24 boxplots, one per industry, each summarising 47
prefecture values. It answers Task 3 of Session 04 visually: the boxes stay wide even
though industry is held fixed, so regional differences survive.

---

# 7. Index: concept to location

| Concept | Where |
|---|---|
| Labour productivity | `src/build_panel.py`, `docs/measurement-framework.md` |
| Value added vs gross output | `docs/measurement-framework.md` §2 |
| Net vs gross value added | `docs/variable-definitions.md` §3 |
| Persons engaged | `docs/variable-definitions.md` |
| Nominal vs real | **gap — see §1.5**, affects the growth figure only |
| Agglomeration economies | motivation for the retired H1; see `docs/measurement-framework.md` §4 |
| Location quotient | `src/build_panel.py`, `src/lq_break_test.py` |
| Herfindahl–Hirschman index | `src/build_panel.py` (`hhi_employment`) |
| MAR vs Jacobs externalities | motivated the retired H1 and H3 |
| Shift-share | `src/shift_share.py`, Chart 6, Session 04 |
| Convergence | §2.7 — tested then withdrawn; confounder for future growth designs |
| Capital deepening | §2.8 — data in `processed_data/*_table3-04.csv`, analysis withdrawn |
| Economic Census comparability gate | `src/econ_census.py` |
| Demographic aging | `src/build_panel.py` (`aging_ratio`) |
| Manufacturing intensity | `src/build_panel.py` |
| Panel data | `processed_data/panel_prefecture_year.csv` |
| Pearson vs Spearman | Sessions 03 and 04 |
| Rank correlation break test | `src/lq_break_test.py` |
| p-values | Sessions 03 and 04 — all withdrawn, see §3.5a |
| **Multiple comparisons** | **§3.5a — 15 tests, 0 survived correction; ended the hypothesis phase** |
| CAGR | Chart 4, national trend |
| Logarithms | `variance_shares()`, Chart 7 |
| Weighted means | Chart 4, variance decomposition |
| Dispersion measures | `notebooks/02_industry_mix_analysis.ipynb` |
| Variance decomposition | `src/shift_share.py`, Session 04 |
| Fixed effects | planned, `README.md` §4 |
| Confounding | Session 04 Finding 4 |
| **Aggregation bias** | **Session 03 error, corrected in Session 04** |
| MNAR / suppression | `src/validate_manufacturing.py` |
| Structural breaks | `docs/data-availability.md` |
| Outliers / negative values | `src/validate_manufacturing.py` |
| Census vs sample survey | `docs/acquisition-log.md` |
| **Reference period vs survey date** | **`docs/reference-years.md`** |
| Disclosure control | `src/validate_manufacturing.py` |
| Control totals | every `metadata/validation_*.json` |
| Published total vs summed parts | `load_prefecture_totals()` |
| JSIC | `docs/variable-definitions.md` |
| Geographic double counting | `src/validate_manufacturing.py` |
| Intercensal estimation | `load_population()` |
| Units | `src/build_panel.py`, `docs/work-log.md` §12.5 |
| Establishment vs enterprise | `docs/variable-definitions.md` |
| Capital intensity | Chart 5 |
| Keiretsu / Aichi | `docs/measurement-framework.md`, Chart 6 |
| CVD-safe palettes | `src/viz_style.py` |
| Log scales, zero baselines, boxplots | Charts 4 and 7 |

---

## The mistakes worth studying

Each taught a concept better than a definition could.

0. **A wrong claim in this very document.** §4.1 originally said 2021 onward was cut
   "for comparability". Checked against the API, the real reason is that the
   successor survey has no area dimension at all. A plausible explanation had been
   recorded as a verified one. The same failure produced the wrong first diagnosis of
   the shift-share bug (§2.5).

1. **The reference-year off-by-one** — reference period is not survey date, and a
   publisher's own metadata field can be wrong. Caught by matching a national total
   across two datasets.
2. **The Session 03 aggregation error** — dispersion measured on aggregates is not
   comparable with dispersion measured on components. Caught by doing the
   decomposition properly.
3. **The shift-share benchmark mismatch** — a decomposition identity only holds
   against the benchmark the decomposition itself uses. Caught by asserting the
   identity instead of trusting plausible-looking output.

---

*This project uses the e-Stat API (政府統計の総合窓口). Its content is not guaranteed
by the Japanese government.*
