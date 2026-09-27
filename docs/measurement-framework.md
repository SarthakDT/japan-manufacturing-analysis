# 02 — Measurement Framework
### Japanese Manufacturing Productivity — Stage 1.1 close-out

> **Status.** Sections 1 and 2 (research question and dependent variable) still stand
> and are the foundation of the project. Section 3 has been updated to list only
> variables actually built. **Section 4's hypotheses were retired in Session 07** and
> the section now records why. The project was originally titled "Japan Manufacturing
> Competitiveness Atlas"; that name was dropped in Session 02 because it described a
> format rather than a finding.

---

## 1. Core Research Question

> **Why are some Japanese prefectures more manufacturing-productive than others?**

Adopting this as the single research question. Productivity is measurable, comparable across all 47 prefectures on a common scale, and — unlike a vaguer "competitiveness" question — doesn't require inventing an arbitrary weighted index before any analysis can start. Everything else in this document exists to make that one question answerable without drift.

---

## 2. Dependent Variable (What are we explaining?)

I did not assume the answer here — I checked what economists and national statistical agencies actually use, and why, rather than defaulting to whichever number is easiest to find.

### Candidate 1: Value Added per Worker

**Pros:**
- This is the actual OECD standard. The OECD's *Measuring Productivity* manual and the 2008 System of National Accounts (SNA §19.47) define labour productivity as value added (or GDP) per hour worked or per worker — not gross output or shipment value.
- Nets out the cost of purchased materials, components, and energy, so it isn't inflated just because a region's industry happens to buy in a lot of intermediate inputs.
- Sums correctly to GDP (GDP = Σ value added across industries), so a prefecture-level productivity measure built this way is consistent with how Japan's own Cabinet Office reports manufacturing's contribution to national GDP.
- Critically for *this specific project*: value-added measures are, per the academic productivity-measurement literature (citing the OECD Productivity Manual, 2001), **less sensitive to outsourcing intensity and the degree of vertical integration** than gross-output-based measures. That matters a lot here, because Aichi's automotive keiretsu (highly vertically integrated — Toyota's own suppliers are headquartered alongside it) and Kumamoto's semiconductor cluster (which imports large amounts of specialized equipment and materials) have structurally different supply chains. A measure that's sensitive to vertical integration would distort exactly the comparison this project wants to make.

**Cons:**
- Less consistently available at fine geographic resolution than shipment value — Japan's e-Stat Census of Manufacture reports both, but value-added figures sometimes come with more lag or coarser industry breakdowns in certain years. This needs to be checked directly in Stage 2, not assumed.
- Value added is itself a *derived* figure (shipments minus several cost categories), so it inherits any inconsistency in how the underlying cost data was collected or reported.
- Worth flagging honestly: some productivity researchers argue that at the individual firm/industry decision-making level, gross-output-based measures are actually the theoretically cleaner choice, because a firm chooses its labor and intermediate-input mix jointly. Value-added is the right choice for this project because we're doing an *aggregate, cross-region comparison*, not analyzing a single firm's production decisions — but it's not a universally "correct" measure in every context, and I'm not going to pretend otherwise.

### Candidate 2: Shipment Value per Worker

**Pros:**
- Far more granular and consistently available — Japan's Census of Manufacture has reported shipment value by prefecture and industry for decades, with fewer gaps than value-added series.
- Simple to explain and communicate.
- Genuinely useful for a different question: it captures scale/capacity of output, which matters if the project ever wants to talk about industrial capacity rather than efficiency.

**Cons:**
- Includes the pass-through value of purchased materials and components — so it's inflated for prefectures/industries that vertically integrate more, and deflated for those that outsource more, for reasons that have nothing to do with actual efficiency. This is a documented bias, not a hypothetical one: "gross output-based labour productivity changes when the ratio of intermediates to labour varies for reasons — such as outsourcing — unrelated either to technology shifts or to efficiency gains" (OECD Productivity Manual, 2001, as cited in the productivity-measurement literature).
- Would specifically corrupt the Aichi-vs-Kumamoto comparison that's central to this project's "Is Japan's Manufacturing Advantage Changing?" narrative, since the two regions differ enormously in vertical integration.
- Doesn't map cleanly onto GDP or any standard national-accounts concept.

### Final Choice

> **Manufacturing Value Added ÷ Manufacturing Employment**

This matches the OECD's standard definition of labour productivity, is consistent with how Japan's own statistics roll up into GDP, and specifically avoids the vertical-integration bias that would otherwise undermine the project's central cross-prefecture, cross-industry comparison. If prefecture-level **value added per hour** turns out to be available in Stage 2, that would be a marginally better variant (it adjusts for part-time/full-time mix) — worth checking, but not worth blocking on. Value added per worker is the safe, well-precedented default, exactly as expected — but now actually verified rather than assumed.

---

## 3. Independent Variables

These are the variables **actually built and validated**, with the column name they
carry in `processed_data/panel_prefecture_year.csv`.

| Concept | Column | Definition | Coverage |
|---|---|---|---|
| Specialization | `lq_top`, `lq_max` | Location quotient on employment shares, 24 JSIC divisions | 2016–2019 |
| Diversity | `hhi_employment` | Herfindahl index over the same 24 divisions | 2016–2019 |
| Demographics | `aging_ratio`, `working_age_share` | 65+ and 15–64 shares of population | 2016–2020 |
| Manufacturing scale | `mfg_intensity` | Manufacturing employment ÷ working-age population | 2016–2020 |
| Capital | — | 有形固定資産額, table 3-04, **30+ establishments only** | 2016–2019 |

Two variables from the original framework were **dropped as unobtainable**: robot
density, for which no credible prefecture-level public series exists, and port
infrastructure, which would need a separate acquisition for weak expected payoff.

One was **replaced**: manufacturing scale was to use total prefectural employment from
the Labour Force Survey, but those are model-based estimates published as reference
values with large prefecture-level sampling error. Working-age population is the
denominator instead — a slightly less natural measure, from a much cleaner source.

---

## 4. Hypotheses — retired, pending replacement

The original framework carried three hypotheses: that specialization raises
productivity (H1), that aging slows productivity growth (H2), and that diversity
raises stability (H3). **All three have been withdrawn.** They are recorded here
because the reasons are worth keeping.

**H1 was never actually tested.** Both available measures — the location quotient of a
prefecture's largest industry, and the Herfindahl index — turned out confounded with
industry composition. They capture *how* specialized a region is without distinguishing
*what it is specialized in*, and the most concentrated prefectures are
disproportionately rural and food-dominated. Testing agglomeration requires holding
industry constant, which prefecture-level measures cannot do.

**H2 came out with the opposite sign** and resisted explanation. Older prefectures grew
faster, not slower. Neither convergence from a low base nor capital deepening absorbed
the effect, and its significance depended on whether the sample covered establishments
with 4+ or 30+ employees.

**H3 was never meaningfully tested.** Volatility estimated from three growth
observations per prefecture carries no information.

**The deeper problem was statistical power, not any single hypothesis.** Fifteen tests
were run across the three, at n = 47, with no correction for multiple comparisons.
Seven reached nominal significance; **none survived Bonferroni or Benjamini-Hochberg**.
With 47 prefectures and a four-year window, hypothesis testing of this kind cannot
distinguish signal from noise.

What the data *can* support is **magnitudes**: exact decompositions, variance shares,
and dispersion comparisons, none of which depend on a significance threshold. New
hypotheses should be designed against that constraint rather than against it.

---

## 5. Data Requirements

| Variable | Unit | Geography | Years needed |
|---|---|---|---|
| Manufacturing Value Added | Yen | Prefecture (ideally × industry) | 2010–2025 |
| Manufacturing Employment | Workers | Prefecture (ideally × industry) | 2010–2025 |
| Manufacturing Shipment Value | Yen | Prefecture × industry | 2010–2025 *(robustness check / fallback if value-added data has gaps)* |
| Industry Employment | Workers | Prefecture × industry | 2010–2025 *(needed to compute LQ)* |
| Total Prefectural Employment | Workers | Prefecture | 2010–2025 *(denominator for manufacturing employment share)* |
| Working-Age Population (15–64) | Persons | Prefecture | 2010–2025 |
| Total Population and 65+ Population | Persons | Prefecture | 2010–2025 *(for the aging ratio)* |

---

## Sources for the dependent-variable decision

- OECD — *Measuring Productivity: Measurement of Aggregate and Industry-Level Productivity Growth* — https://www.oecd.org/std/productivity-stats/2352458.pdf
- OECD — Labour productivity defined as GDP/value added per hour worked (2008 SNA §19.47) — https://www.oecd.org/en/publications/oecd-compendium-of-productivity-indicators-2018_pdtvy-2018-en/full-report/component-9.html
- Bardazzi, R. — *The measurement of productivity: contributions to the analysis from IO economics* (cites OECD Productivity Manual 2001 on value-added vs. gross-output bias) — https://www.iioa.org/conferences/19th/papers/files/569_20110530111_BARDAZZIDRAFTMAY30.doc
- Fevereiro, Bastos & Freitas — *Labour Productivity in Vertically Integrated Sectors: An Empirical Study for Brazil* (IIOA conference paper, on outsourcing bias in conventional productivity measures) — https://www.iioa.org/conferences/25th/papers/files/2975_20170516081_LabourproductivityinVerticallyIntegratedSectors-AnempiricalstudyforBrasil(IIOA).pdf
- Malaysia DOSM — Labour Productivity technical notes (confirms value-added/employment methodology per UN SNA 2008 and OECD manual) — https://storage.dosm.gov.my/technotes/productivity.pdf
- IMPLAN — *Output, Value Added, and Double Counting* (plain-language explanation of why value added avoids double-counting across a supply chain) — https://support.implan.com/hc/en-us/articles/360025171053-Output-Value-Added-and-Double-Counting
