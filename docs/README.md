# Documentation

Reference material for the Japanese manufacturing productivity project. Start with
whichever question you have.

## Understanding the analysis

| Document | What it answers |
|---|---|
| [concepts.md](concepts.md) | Every statistical, economic and manufacturing concept used, from first principles, with worked examples and pointers to where each was applied. ~50 entries. |
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
| [work-log.md](work-log.md) | Chronological development record across seven sessions, including dead ends, bugs and corrections. Long, and deliberately preserves mistakes rather than tidying them away. |

## Three things worth reading even if you skip everything else

**The year labels are wrong in the source.** e-Stat labels Census of Manufacture
datasets by survey year, but from the 2017 survey the financial items refer to the
previous calendar year. e-Stat's own `SURVEY_DATE` metadata field is wrong for every
survey since. See [reference-years.md](reference-years.md).

**Suppressed cells are not zeros.** Confidentiality suppression is
missing-not-at-random, concentrated in thin prefecture × industry cells. Zero-filling
would distort exactly the cells a location quotient depends on. See
[concepts.md](concepts.md) §3.14.

**The hypothesis-testing phase was withdrawn.** Fifteen tests at n = 47 with no
correction for multiple comparisons; none survived it. The project now reports
magnitudes rather than significance. See [concepts.md](concepts.md) §3.5a and
[measurement-framework.md](measurement-framework.md) §4.
