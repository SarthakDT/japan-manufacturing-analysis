# Japanese Manufacturing Productivity

Why are some Japanese prefectures more manufacturing-productive than others?

---

## 1. Problem Statement

Japan's manufacturing output is highly concentrated by region, but output share and
productivity are not the same thing. This project measures manufacturing value added per
worker across all 47 prefectures and 24 industry divisions for 2016–2019, and asks
whether the differences between regions reflect where production happens or simply what
each region happens to make.

The dependent variable is value added per worker, following the OECD *Measuring
Productivity* manual and SNA 2008 §19.47. Value added is preferred to gross output
because it is far less sensitive to vertical integration and outsourcing intensity,
which matters when comparing a vertically integrated automotive cluster against an
import-heavy electronics one.

Every statistical, economic and manufacturing concept used here is defined from
first principles, with worked examples and pointers to where it was applied, in
[docs/CONCEPTS.md](docs/CONCEPTS.md).

## 2. Data Sources

**METI Census of Manufacture** (工業統計調査) via the e-Stat API — establishments,
persons engaged, shipments and value added by prefecture × industry.

Indexed by **reference year, not survey year.** e-Stat labels these datasets by survey
year, but from the 2017 survey onward the financial items refer to the *previous*
calendar year, so the dataset titled `2019年確報` contains 2018 value added. This was
verified numerically rather than assumed, and e-Stat's own `SURVEY_DATE` metadata field
is wrong for every survey from 2017 onward.

**Statistics Bureau intercensal adjusted population** (国勢調査結果による補間補正人口) —
prefecture population by three age bands, chosen over the forward-projected estimates
because 2016–2019 sits between the 2015 and 2020 censuses and is reconciled against both.

**2021 Economic Census** (令和3年経済センサス‐活動調査) supplies reference year 2020.
It reproduces the Census of Manufacture basis exactly — zero difference across all 47
prefectures on 2019, verified before appending.

The panel **ends at reference year 2020**, and that is a data limit rather than a
scope decision: the successor Economic Structure Survey publishes manufacturing with
no area dimension, so value added by prefecture does not exist for 2021 onward.

Confidentiality-suppressed cells are held as missing and never zero-filled: suppression
targets thin prefecture × industry cells, so zero-filling would distort exactly the
small-industry cells a location quotient depends on.

## 3. Key Findings

These are **magnitudes and decompositions**, not significance tests. With 47
prefectures and a five-year window there is not enough power for hypothesis testing to
distinguish signal from noise, so the project reports quantities that do not depend on
a p-value. See the note on statistical power below.

1. **Japan's largest manufacturing region is not its most productive.** Aichi produces
   12.8% of national manufacturing value added and ranks 7th of 47 on value added per
   worker. Tokyo ranks 27th, Osaka 22nd.

2. **Productivity differs 5.90× between manufacturing industries**, from petroleum and
   coal at 34.8 million yen per worker to leather at 5.9, against a national average
   of 13.0.

3. **Large regional differences survive once industry is held fixed.** Within a single
   industry the best prefecture out-produces the worst by a median of **6.62×**, and 14
   of 24 industries individually exceed the entire between-industry spread.

4. **Productive prefectures beat their peers rather than simply holding better
   industries.** An exact shift-share decomposition attributes more of the gap to
   within-industry performance than to industry mix in 37 of 47 prefectures, stable in
   every year from 2016 to 2019.

5. **Industry identity explains more at cell level than prefecture identity does**
   (51.6% against 15.0% of variance in log productivity), while the aggregate
   decomposition points the other way. Both hold: prefectures are too diversified
   (Herfindahl 0.06 to 0.25) for between-industry differences to reach their totals.

6. **Nominal productivity was flat**, growing 0.34% a year from 2016 to 2019 and
   essentially unchanged in 2020. Nothing has been deflated, so real growth may be lower.

### A note on statistical power

An earlier version of this project tested three hypotheses about specialization, aging
and diversity across 15 correlation and regression tests. Seven reached nominal
significance at 0.05; **none survived correction for multiple comparisons** under either
Bonferroni or Benjamini-Hochberg. Those findings have been withdrawn rather than
reported with caveats, and new hypotheses are being designed against what n = 47
actually supports. See `02_Measurement_Framework.md` §4.

## 4. Next Steps

**New hypotheses, designed around the power constraint.** The descriptive work points to
one well-posed question: given that substantial within-industry variation exists across
prefectures (Finding 3), what explains it? Any hypothesis must hold industry constant,
because prefecture-level measures confound how specialized a region is with what it is
specialized in.

The natural specification uses the prefecture × industry panel rather than prefecture
aggregates, which raises the sample from 47 to 1,128 observations per year:

```
log(value added per worker)_pi  =  β · X_pi  +  industry FE  +  ε_pi
```

with standard errors clustered by prefecture, and table 3-03 (30+ employees, clean net
value added) as a robustness check alongside the primary 4+ series.

**Known limitations to design around.** Value added is nominal and never deflated.
Productivity is per worker, not per hour, as hours are unpublished at this granularity.
Capital exists only for 30+ establishments. The panel ends at reference year 2020
permanently, because the successor survey publishes no prefecture breakdown.

---

*This project uses the e-Stat API (政府統計の総合窓口). Its content is not guaranteed by
the Japanese government.*
