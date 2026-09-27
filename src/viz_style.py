"""
viz_style.py — shared chart styling, palette, and Japanese→romaji label maps.

Palette values come from a validated categorical set. The two series colors used
throughout (blue, orange) were checked with the data-viz palette validator under
`--pairs all` on the light surface and clear every gate:

    lightness band PASS · chroma floor PASS
    CVD separation  ΔE 24.7 (protan), 32.7 (tritan)
    normal-vision   ΔE 33.6
    contrast        both ≥ 3:1

A third slot (aqua #1baf7a) was deliberately NOT adopted: it passes separation
but sits at 2.74:1 contrast, which triggers a relief obligation. Two colors plus
a recessive gray covers every chart here, so the third slot buys nothing.

Encoding convention, held across all four charts:
    blue   = the data
    orange = the subject of the chart's question (emphasis)
    gray   = de-emphasised context

Labels are romanised because the audience is English-reading and because it
removes any dependency on a CJK font being installed.
"""

from __future__ import annotations

import matplotlib as mpl

# --- palette -----------------------------------------------------------------

SURFACE = "#fcfcfb"      # chart surface
INK = "#0b0b0b"          # primary text
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"    # axis labels, de-emphasised marks
GRID = "#e1e0d9"         # hairline gridline
AXIS = "#c3c2b7"         # baseline

BLUE = "#2a78d6"         # categorical slot 1 — the data
ORANGE = "#eb6834"       # categorical slot 2 — emphasis
GRAY_MARK = "#b8b6ae"    # recessive scatter points

# --- labels ------------------------------------------------------------------

ROMAJI = {
    "北海道": "Hokkaido", "青森": "Aomori", "岩手": "Iwate", "宮城": "Miyagi",
    "秋田": "Akita", "山形": "Yamagata", "福島": "Fukushima", "茨城": "Ibaraki",
    "栃木": "Tochigi", "群馬": "Gunma", "埼玉": "Saitama", "千葉": "Chiba",
    "東京": "Tokyo", "神奈川": "Kanagawa", "新潟": "Niigata", "富山": "Toyama",
    "石川": "Ishikawa", "福井": "Fukui", "山梨": "Yamanashi", "長野": "Nagano",
    "岐阜": "Gifu", "静岡": "Shizuoka", "愛知": "Aichi", "三重": "Mie",
    "滋賀": "Shiga", "京都": "Kyoto", "大阪": "Osaka", "兵庫": "Hyogo",
    "奈良": "Nara", "和歌山": "Wakayama", "鳥取": "Tottori", "島根": "Shimane",
    "岡山": "Okayama", "広島": "Hiroshima", "山口": "Yamaguchi", "徳島": "Tokushima",
    "香川": "Kagawa", "愛媛": "Ehime", "高知": "Kochi", "福岡": "Fukuoka",
    "佐賀": "Saga", "長崎": "Nagasaki", "熊本": "Kumamoto", "大分": "Oita",
    "宮崎": "Miyazaki", "鹿児島": "Kagoshima", "沖縄": "Okinawa",
}

# JSIC 2-digit manufacturing divisions, short English labels for chart use.
INDUSTRY_EN = {
    "09": "Food", "10": "Beverages & tobacco", "11": "Textiles",
    "12": "Wood products", "13": "Furniture", "14": "Pulp & paper",
    "15": "Printing", "16": "Chemicals", "17": "Petroleum & coal",
    "18": "Plastics", "19": "Rubber", "20": "Leather",
    "21": "Ceramics & stone", "22": "Iron & steel", "23": "Non-ferrous metals",
    "24": "Fabricated metal", "25": "General machinery", "26": "Production machinery",
    "27": "Business machinery", "28": "Electronic components", "29": "Electrical machinery",
    "30": "Info & comms equipment", "31": "Transport equipment", "32": "Other manufacturing",
}


def apply_style() -> None:
    """Set matplotlib defaults: thin marks, hairline solid grid, recessive chrome."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.bbox": "tight",
        "savefig.dpi": 200,
        "figure.dpi": 110,

        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
        "font.size": 10,

        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        # Must clear the deck line that subtitle() draws at 1.02 axes fraction,
        # otherwise the two overlap.
        "axes.titlepad": 32,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,

        # Solid hairline gridlines, one shade off the surface. Never dashed.
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "grid.alpha": 1.0,
        "axes.axisbelow": True,

        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.major.size": 0,
        "ytick.major.size": 0,

        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": INK_SECONDARY,

        "lines.linewidth": 2.0,
        "lines.markersize": 8,
    })


def subtitle(ax, text: str) -> None:
    """Deck line under the title, in secondary ink."""
    ax.annotate(text, xy=(0, 1.02), xycoords="axes fraction",
                fontsize=9.5, color=INK_SECONDARY, va="bottom", ha="left")


def source_note(fig, text: str) -> None:
    """Source/definition footnote in muted ink, bottom-left."""
    fig.text(0.0, -0.035, text, fontsize=8, color=INK_MUTED, ha="left", va="top")
