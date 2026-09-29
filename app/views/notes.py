import streamlit as st

st.title("Notes")

st.markdown("""
**Who this is for.** An illustrative use case: a prefectural government planner
benchmarking the prefecture's manufacturing sector. It is a portfolio project, not
commissioned work.

**The measure.** Value added per worker: gross output minus purchased inputs, per
person engaged, in million yen. **Nominal** (never deflated) and **per worker, not per
hour**, since hours are not published at this granularity.

**Aggregation.** Any group figure is total value added divided by total employment,
never an average of prefecture ratios.

**Shift-share decomposition.** A prefecture's gap to the national benchmark splits
exactly into:
- *industry mix*: which industries it hosts, valued at national rates
- *within-industry performance*: how its industries perform against the same industries nationally

The benchmark is national value added per worker over the industries the prefecture
has, so the identity holds to machine precision.

**Suppression.** Some prefecture x industry cells are withheld for confidentiality.
They are missing, never zero. The decomposition uses published cells only; a final
*suppression adjustment* reconciles it to the published prefecture total.

**Diagnosis quadrants** are the signs of the two effects. They say where a gap sits,
not what causes it or what to do.

**Years.** 2016-2019 come from the Census of Manufacture, and each edition is labelled
one year after the data it holds. 2020 comes from the 2021 Economic Census, which has
no industry detail. The series ends in 2020 permanently: the successor survey publishes
no prefecture breakdown.

**Source and attribution.** METI Census of Manufacture (工業統計調査) and the 2021
Economic Census for Business Activity, via the e-Stat API.

> この分析は、政府統計総合窓口(e-Stat)のAPI機能を使用していますが、サービスの内容は国によって保証されたものではありません。

This service uses the e-Stat API; its content is not guaranteed by the Japanese government.

Code, method and data pipeline:
[github.com/SarthakDT/japan-manufacturing-analysis](https://github.com/SarthakDT/japan-manufacturing-analysis)
""")
