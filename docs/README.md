# Documentation

Reference material for the Japanese manufacturing productivity project. Start with
whichever question you have.

## Start here

| Document | What it answers |
|---|---|
| [executive-summary.md](executive-summary.md) | The one-page version for the stakeholder, a prefectural planner: what the data shows, the diagnostic, and what it cannot tell you. |

## Dashboards

| Document | What it answers |
|---|---|
| [../dashboard/POWER_BI_GUIDE.md](../dashboard/POWER_BI_GUIDE.md) | How to build the Power BI report: import, data model, DAX measures with the reason for each, page layouts, publishing, and a checklist. |
| [../dashboard/expected_values.md](../dashboard/expected_values.md) | The figures a correct dashboard must show. Generated, and checked automatically against the Streamlit app. |
| `app/` | The Streamlit app: `streamlit run app/streamlit_app.py`. |

## Understanding the analysis

| Document | What it answers |
|---|---|
| [concepts.md](concepts.md) | Every statistical, economic, manufacturing and data-engineering concept used, from first principles, with worked examples and pointers to where each was applied. 78 entries, each with a **Learn more** reading list. §8 covers business intelligence: the star schema in Power BI, DAX, ratio of sums, CI and Streamlit. |
| [measurement-framework.md](measurement-framework.md) | Why value added per worker is the dependent variable, which independent variables were built, and why the original hypotheses were retired. |

## Understanding the data

| Document | What it answers |
|---|---|
| [reference-years.md](reference-years.md) | Why a dataset labelled `2019年確報` contains 2018 data, and how that was proven. **Read this before using any year label.** |
| [variable-definitions.md](variable-definitions.md) | Japanese variable names, units, the two value-added definitions, and missing-value conventions. |
| [data-availability.md](data-availability.md) | Which reference years exist, from which table, and why the panel ends at 2020 permanently. |
| [acquisition-log.md](acquisition-log.md) | What was downloaded, when, from which statsDataId, and what went wrong. |

## Understanding how it was built

| Document | What it answers |
|---|---|
| [work-log.md](work-log.md) | Chronological development record across nine sessions, including dead ends, bugs and corrections. Long, and deliberately preserves mistakes rather than tidying them away. |

## Analysis notebooks

| Notebook | What it does |
|---|---|
| `notebooks/01_exploratory_analysis.ipynb` | Levels, spread, rankings, national trend |
| `notebooks/02_industry_mix_analysis.ipynb` | Shift-share decomposition and variance shares |
| `notebooks/03_prefecture_typology.ipynb` | Appendix A: clustering, with a verdict that it is only provisional |
| `notebooks/04_anomaly_detection.ipynb` | Appendix B: median polish, residual surface (feeds the dashboard's "beats or misses expectation") |

## Three things worth reading even if you skip everything else

**The year labels are wrong in the source.** e-Stat labels Census of Manufacture
datasets by survey year, but from the 2017 survey the financial items refer to the
previous calendar year. e-Stat's own `SURVEY_DATE` metadata field is wrong for every
survey since. See [reference-years.md](reference-years.md).

**Suppressed cells are not zeros.** Confidentiality suppression is
missing-not-at-random, concentrated in thin prefecture × industry cells. Zero-filling
would distort exactly the cells a location quotient depends on. See
[concepts.md](concepts.md) §3.14.

**The hypothesis-testing phase was withdrawn.** The original 15 tests at n = 47
produced nominally significant results that did not survive correction for multiple
comparisons, so the project does not treat those associations as robust evidence. The project now reports
magnitudes rather than significance. See [concepts.md](concepts.md) §3.5a and
[measurement-framework.md](measurement-framework.md) §4.
