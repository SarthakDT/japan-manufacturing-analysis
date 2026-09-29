"""
common.py — data access, the one aggregation rule, and chart styling for the app.

WHAT THE APP IS ALLOWED TO COMPUTE
Nothing analytical. Shift-share, location quotients, residuals, ranks and the
diagnosis all arrive precomputed in dashboard/data/, written by
src/build_dashboard_data.py, which is also what the Power BI report reads. The
only arithmetic here is aggregating a selection, and that follows one rule:

    value added per worker of a group = SUM(value added) / SUM(employment)

never the mean of the per-prefecture ratio. The mean weights Tottori the same
as Aichi and gives a national figure that no statistical office would publish.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dashboard" / "data"

sys.path.insert(0, str(ROOT / "src"))
from viz_style import (AXIS, BLUE, GRAY_MARK, GRID, INK, INK_MUTED,  # noqa: E402
                       INK_SECONDARY, ORANGE, SURFACE)

DETAIL_YEARS = [2016, 2017, 2018, 2019]
UNIT = "million yen per worker"

# Codes are identifiers, not numbers: "09" must stay "09" or every join breaks.
CODE_DTYPES = {"prefecture_code": str, "industry_code": str, "top_industry_code": str}


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv", dtype=CODE_DTYPES, encoding="utf-8-sig")


def prefectures() -> pd.DataFrame:
    return load("dim_prefecture")


def industries() -> pd.DataFrame:
    return load("dim_industry")


def prefecture_year(year: int) -> pd.DataFrame:
    f = load("fact_prefecture_year")
    return f[f.reference_year == year].merge(prefectures(), on="prefecture_code")


def va_per_worker(df: pd.DataFrame) -> float:
    """Ratio of sums. The only aggregation rule the app uses."""
    return float(df.value_added.sum() / df.employment.sum())


def selected_year() -> int:
    return int(st.session_state.get("year", DETAIL_YEARS[-1]))


def signed(v: float) -> str:
    # Round first so a tiny negative prints as +0.00, not -0.00.
    return f"{round(v, 2) + 0.0:+.2f}"


# --- chart styling -------------------------------------------------------------

def style(fig: go.Figure, height: int = 420) -> go.Figure:
    """The project's chart conventions, matched to src/viz_style.py."""
    fig.update_layout(
        height=height,
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Segoe UI, DejaVu Sans, Arial, sans-serif", size=12,
                  color=INK_SECONDARY),
        title_font=dict(color=INK, size=15),
        title_x=0.01, title_xanchor="left",  # left-aligned, as in the static charts
        # Room for tick labels plus axis titles; tighter margins clipped the
        # minus signs off negative ticks.
        margin=dict(l=80, r=20, t=50, b=70),
        showlegend=False,
        hoverlabel=dict(bgcolor="white", font_color=INK),
    )
    fig.update_xaxes(automargin=True, gridcolor=GRID, zerolinecolor=AXIS, linecolor=AXIS,
                     tickfont_color=INK_MUTED, title_font_color=INK_SECONDARY)
    fig.update_yaxes(automargin=True, gridcolor=GRID, zerolinecolor=AXIS, linecolor=AXIS,
                     tickfont_color=INK_MUTED, title_font_color=INK_SECONDARY)
    return fig


def show(fig: go.Figure, key: str) -> None:
    # theme=None keeps the project palette instead of Streamlit's default theme.
    st.plotly_chart(fig, theme=None, width="stretch", key=key,
                    config={"displayModeBar": False})


__all__ = ["AXIS", "BLUE", "GRAY_MARK", "GRID", "INK", "INK_MUTED", "INK_SECONDARY",
           "ORANGE", "SURFACE", "DETAIL_YEARS", "UNIT", "load", "prefectures",
           "industries", "prefecture_year", "va_per_worker", "selected_year",
           "signed", "style", "show"]
