import plotly.graph_objects as go
import streamlit as st

from common import (AXIS, BLUE, DETAIL_YEARS, INK_MUTED, ORANGE, prefecture_year,
                    selected_year, show, style)

year = selected_year()
st.title("Diagnosis: is the gap about industries, or performance?")

if year not in DETAIL_YEARS:
    st.info(f"No diagnosis exists for {year}: the 2021 Economic Census has no prefecture x "
            "industry detail. Pick 2016-2019 in the sidebar.")
    st.stop()

df = prefecture_year(year)
pref = st.session_state.get("focus_prefecture", "Aichi")

fig = go.Figure()
others = df[df.name_en != pref]
me = df[df.name_en == pref]
size = lambda s: 8 + 40 * (s / df.employment.max()) ** 0.5  # noqa: E731  diameter ~ sqrt, so area tracks employment
for part, color, opacity in [(others, BLUE, 0.65), (me, ORANGE, 1.0)]:
    fig.add_scatter(
        x=part.mix_effect, y=part.within_effect, mode="markers+text" if part is me else "markers",
        text=part.name_en if part is me else None, textposition="top center",
        marker=dict(size=size(part.employment), color=color, opacity=opacity,
                    line=dict(color="white", width=1)),
        customdata=part[["name_en", "diagnosis", "va_per_worker"]],
        hovertemplate="<b>%{customdata[0]}</b><br>mix %{x:+.2f}, within %{y:+.2f}"
                      "<br>VA per worker %{customdata[2]:.2f}<br>%{customdata[1]}<extra></extra>")
fig.add_hline(y=0, line_color=AXIS, line_width=1)
fig.add_vline(x=0, line_color=AXIS, line_width=1)
lim_x = df.mix_effect.abs().max() * 1.15
lim_y = df.within_effect.abs().max() * 1.15
for x, y, label, xa, ya in [
        (lim_x, lim_y, "Strong mix, strong performance", "right", "top"),
        (-lim_x, lim_y, "Weak mix, strong performance", "left", "top"),
        (lim_x, -lim_y, "Strong mix, weak performance", "right", "bottom"),
        (-lim_x, -lim_y, "Weak mix, weak performance", "left", "bottom")]:
    fig.add_annotation(x=x, y=y, text=label, showarrow=False, xanchor=xa, yanchor=ya,
                       font=dict(color=INK_MUTED, size=11))
fig.update_xaxes(title="Industry mix effect (which industries it hosts)",
                 range=[-lim_x, lim_x], zeroline=False)
fig.update_yaxes(title="Within-industry effect (how they perform)",
                 range=[-lim_y, lim_y], zeroline=False)
fig.update_layout(title=f"All 47 prefectures, {year}. Bubble area = manufacturing employment")
show(style(fig, height=620), key="diagnosis_scatter")

st.caption(f"Highlighted: **{pref}** (change it on the Prefecture benchmark page). "
           "Both axes in million yen per worker, relative to the national benchmark.")

counts = df.diagnosis.value_counts()
look = {
    "Strong mix, strong performance": "Protect what works",
    "Weak mix, strong performance": "The industry base, not the firms",
    "Strong mix, weak performance": "Performance inside the industries held",
    "Weak mix, weak performance": "Both",
}
st.dataframe(
    [{"Diagnosis": k, "Prefectures": int(counts.get(k, 0)), "Where to look first": v,
      "Examples": ", ".join(df[df.diagnosis == k].nlargest(3, "employment").name_en)}
     for k, v in look.items()],
    hide_index=True)

st.warning(
    "**Diagnostic, not prescriptive.** The within-industry term is not purely firm "
    "efficiency. A 2-digit industry bundles very different products, so a within-industry "
    "advantage in chemicals may mean making petrochemicals rather than cosmetics; it also "
    "picks up plant scale and the age of the capital stock. The chart says where to look, "
    "not what to do.", icon=":material/info:")
