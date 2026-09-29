import plotly.graph_objects as go
import streamlit as st

from common import (BLUE, DETAIL_YEARS, GRAY_MARK, INK, ORANGE, UNIT, industries, load,
                    prefecture_year, selected_year, show, signed, style, va_per_worker)

year = selected_year()
df = prefecture_year(year)

st.title("Prefecture benchmark")

names = df.sort_values("prefecture_code").name_en.tolist()
# Kept under a plain session key, not the widget's own: Streamlit clears a
# widget's state when the page that draws it is left, and the Diagnosis page
# highlights whichever prefecture was chosen here.
pref = st.selectbox("Prefecture", names,
                    index=names.index(st.session_state.get("focus_prefecture", "Aichi")))
st.session_state["focus_prefecture"] = pref
r = df.set_index("name_en").loc[pref]
national = va_per_worker(df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("VA per worker", f"{r.va_per_worker:.2f}",
          delta=f"{r.va_per_worker - national:+.2f} vs national {national:.2f}", border=True)
c2.metric("Rank", f"{int(r.rank_va_per_worker)} of 47", border=True)
c3.metric("Share of national value added", f"{r.share_of_national_va:.2%}", border=True)
c4.metric("Diagnosis", r.diagnosis if isinstance(r.diagnosis, str) else "n/a", border=True)

if year not in DETAIL_YEARS:
    st.info(f"{year} comes from the 2021 Economic Census, which publishes prefecture totals "
            "but no prefecture x industry detail. The decomposition needs that detail, so "
            f"only the headline figures above exist for {year}. Pick 2016-2019 in the sidebar.")
    st.stop()

# --- the waterfall -------------------------------------------------------------
st.subheader("Why this prefecture differs from the national benchmark")
wf = load("fact_waterfall")
code = r.prefecture_code
steps = wf[(wf.reference_year == year) & (wf.prefecture_code == code)].sort_values("step_order")

c1, c2 = st.columns([3, 2])
with c1:
    fig = go.Figure(go.Waterfall(
        x=steps.step.tolist() + ["Published VA per worker"],
        y=steps.amount.tolist() + [0],
        measure=["absolute", "relative", "relative", "relative", "total"],
        text=[f"{steps.amount.iloc[0]:.2f}"] + [signed(v) for v in steps.amount.iloc[1:]]
             + [f"{r.va_per_worker:.2f}"],
        textposition="outside",
        increasing_marker_color=BLUE, decreasing_marker_color=ORANGE,
        totals_marker_color=GRAY_MARK, connector_line_color=GRAY_MARK,
        hovertemplate="%{x}: %{text}<extra></extra>"))
    top = max(steps.amount.cumsum().max(), r.va_per_worker) * 1.15
    fig.update_yaxes(title=UNIT, range=[0, top])
    fig.update_layout(title=f"{pref}, {year}")
    show(style(fig, height=420), key="benchmark_waterfall")
with c2:
    st.metric("Industry mix", signed(r.mix_effect),
              help="What the prefecture would gain or lose if each of its industries "
                   "performed at the national rate: the effect of which industries it hosts.")
    st.metric("Within-industry performance", signed(r.within_effect),
              help="How far its industries beat or trail the national rate for the same "
                   "industry, weighted by its own employment.")
    st.metric("Suppression adjustment", signed(r.suppression_adjustment),
              help="Some prefecture x industry cells are withheld for confidentiality. The "
                   "decomposition can only use published cells; this step closes the gap "
                   "to the published prefecture total, which includes them.")
    st.caption("Benchmark: national value added per worker over the same industries this "
               "prefecture has. The steps sum exactly to the published figure.")

# --- industry mix ----------------------------------------------------------------
st.subheader("Which industries it holds, against the national mix")
cells = load("fact_prefecture_industry")
c = (cells[(cells.reference_year == year) & (cells.prefecture_code == code)]
     .merge(industries(), on="industry_code"))
c = c[c.employment.fillna(0) > 0].sort_values("employment_share")
fig = go.Figure()
fig.add_bar(y=c.name_en, x=c.national_employment_share, orientation="h",
            name="National", marker_color=GRAY_MARK,
            hovertemplate="%{y}: %{x:.1%} nationally<extra></extra>")
fig.add_bar(y=c.name_en, x=c.employment_share, orientation="h", name=pref,
            marker_color=BLUE, customdata=c.lq,
            hovertemplate="%{y}: %{x:.1%} of " + pref
                          + " workers<br>location quotient %{customdata:.2f}<extra></extra>")
fig.update_layout(barmode="group", showlegend=True, bargap=0.25,
                  legend=dict(orientation="h", y=1.02, x=0, yanchor="bottom",
                              font_color=INK))
fig.update_xaxes(title="share of manufacturing employment", tickformat=".0%")
style(fig, height=640).update_layout(showlegend=True, margin_t=70)
show(fig, key="benchmark_mix")

# --- residuals -----------------------------------------------------------------
st.subheader("Industries that beat or miss expectation")
st.caption("Expectation = what this prefecture's general level and the industry's national "
           "level together predict (median polish of log value added per worker). A cell "
           "beating it is doing better than both its region and its industry would suggest.")
res = c.dropna(subset=["residual_log"]).sort_values("pct_vs_expected", ascending=False)
table = res[["name_en", "va_per_worker", "pct_vs_expected", "employment"]].rename(columns={
    "name_en": "Industry", "va_per_worker": "VA per worker",
    "pct_vs_expected": "vs expected", "employment": "Workers"})
cfg = {"VA per worker": st.column_config.NumberColumn(format="%.2f"),
       "vs expected": st.column_config.NumberColumn(format="percent"),
       "Workers": st.column_config.NumberColumn(format="localized")}
a, b = st.columns(2)
with a:
    st.markdown("**Above expectation**")
    st.dataframe(table.head(5), hide_index=True, column_config=cfg)
with b:
    st.markdown("**Below expectation**")
    st.dataframe(table.tail(5).iloc[::-1], hide_index=True, column_config=cfg)
st.caption("Cells with suppressed value added, or non-positive value added (which has no "
           "log), are not scored.")
