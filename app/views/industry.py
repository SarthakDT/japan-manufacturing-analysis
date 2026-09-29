import plotly.graph_objects as go
import streamlit as st

from common import (BLUE, DETAIL_YEARS, INK_MUTED, ORANGE, UNIT, industries, load,
                    selected_year, show, style)

year = selected_year()
st.title("Industry context")

if year not in DETAIL_YEARS:
    st.info(f"No industry detail exists for {year}. Pick 2016-2019 in the sidebar.")
    st.stop()

f = load("fact_industry_year")
d = f[f.reference_year == year].merge(industries(), on="industry_code")

st.caption("Which industry a region hosts matters because industries differ far more than "
           "regions do on value added per worker.")
ranked = d.sort_values("national_va_per_worker")
fig = go.Figure(go.Bar(
    x=ranked.national_va_per_worker, y=ranked.name_en, orientation="h", marker_color=BLUE,
    hovertemplate="%{y}: %{x:.2f} " + UNIT + "<extra></extra>"))
spread = ranked.national_va_per_worker.iloc[-1] / ranked.national_va_per_worker.iloc[0]
fig.update_layout(title=f"National value added per worker by industry, {year} "
                        f"({spread:.1f}x from lowest to highest)")
fig.update_xaxes(title=UNIT)
show(style(fig, height=640), key="industry_rank")

st.subheader("Capital intensity against value added per worker")
# Spearman's rho is the Pearson correlation of the ranks.
rho = d[["capital_per_worker_30plus", "va_per_worker_30plus"]].rank().corr().iloc[0, 1]
# Label only the extremes and transport equipment (Japan's largest industry);
# the dense middle is readable on hover. Labelling all 24 made them collide.
d["label"] = [n if (va >= 25 or cap >= 30 or va <= 8 or code == "31") else ""
              for n, va, cap, code in zip(d.name_en, d.va_per_worker_30plus,
                                          d.capital_per_worker_30plus, d.industry_code)]
fig = go.Figure(go.Scatter(
    x=d.capital_per_worker_30plus, y=d.va_per_worker_30plus, mode="markers+text",
    text=d.label, textposition="top center", textfont=dict(size=11, color=INK_MUTED),
    customdata=d.name_en,
    marker=dict(size=10, color=ORANGE, line=dict(color="white", width=1)),
    hovertemplate="<b>%{customdata}</b><br>capital %{x:.1f}, VA %{y:.2f}<extra></extra>"))
fig.update_xaxes(title="Tangible fixed assets per worker, million yen (log scale)", type="log",
                 tickvals=[3, 5, 10, 20, 50, 100, 200])
fig.update_yaxes(title=UNIT)
fig.update_layout(title=f"24 industries, {year}. Spearman rank correlation {rho:+.2f}")
show(style(fig, height=560), key="industry_capital")
st.caption("Establishments with 30+ employees only, the coverage of the capital data, and "
           "only cells where capital, employment and value added are all published. Across "
           "industries, capital and value added per worker rank together (+0.63 to +0.73 "
           "depending on the year). Across prefectures, capital deepening explained nothing: "
           "industry is where capital matters.")
