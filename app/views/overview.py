import plotly.graph_objects as go
import streamlit as st

from common import (BLUE, INK_MUTED, ORANGE, UNIT, prefecture_year, selected_year,
                    show, style, va_per_worker)

year = selected_year()
df = prefecture_year(year)

st.title("Where does a prefecture's manufacturing gap come from?")
st.caption(f"Reference year {year}. Value added per worker across Japan's 47 prefectures, "
           f"{UNIT}, nominal.")

regions = df.sort_values("region_order").region.unique().tolist()
picked = st.multiselect("Region", regions, placeholder="All regions")
sel = df[df.region.isin(picked)] if picked else df

national = va_per_worker(df)
c1, c2, c3, c4 = st.columns(4)
if picked:
    group = va_per_worker(sel)
    c1.metric("VA per worker, selected regions", f"{group:.2f}",
              delta=f"{group - national:+.2f} vs national", border=True)
else:
    c1.metric("VA per worker, national", f"{national:.2f}", border=True)
c2.metric("Manufacturing workers", f"{sel.employment.sum() / 1e6:.2f}m", border=True)
c3.metric("Value added", f"¥{sel.value_added.sum() / 1e6:.1f}tn", border=True)
c4.metric("Share of national value added",
          f"{sel.value_added.sum() / df.value_added.sum():.1%}", border=True)

# Ranked bar of all 47. Selected regions are drawn in orange, the rest recede,
# so the ranking context is never lost when filtering.
ranked = df.sort_values("va_per_worker")
colors = [ORANGE if (picked and r in picked) else BLUE for r in ranked.region]
if picked:
    colors = [c if c == ORANGE else "#c9d9f0" for c in colors]
fig = go.Figure(go.Bar(
    x=ranked.va_per_worker, y=ranked.name_en, orientation="h", marker_color=colors,
    customdata=ranked[["rank_va_per_worker", "region"]],
    hovertemplate="<b>%{y}</b> (%{customdata[1]})<br>%{x:.2f} " + UNIT
                  + "<br>rank %{customdata[0]} of 47<extra></extra>"))
fig.add_vline(x=national, line_color=INK_MUTED, line_width=1, line_dash="dot",
              annotation_text=f"national {national:.2f}", annotation_position="bottom right",
              annotation_font_color=INK_MUTED)
fig.update_layout(title="Value added per worker, all 47 prefectures")
fig.update_xaxes(title=UNIT)
fig.update_yaxes(tickfont_size=10)
show(style(fig, height=900), key="overview_rank")

st.caption("The leaders are mostly mid-sized prefectures running capital-intensive process "
           "industries, not the largest manufacturing regions. Aichi, with 12.8% of national "
           "value added in 2019, ranks 7th. Use **Prefecture benchmark** to see why a "
           "prefecture sits where it does.")
