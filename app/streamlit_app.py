"""
Japanese manufacturing: where does a prefecture's gap come from?

Streamlit front-end over dashboard/data/, the same extract the Power BI report
reads. Run from the repository root:

    streamlit run app/streamlit_app.py
"""

import streamlit as st

from common import DETAIL_YEARS, load

st.set_page_config(page_title="Prefecture manufacturing benchmark",
                   page_icon=":material/factory:", layout="wide")

years = load("dim_year")
all_years = years.reference_year.tolist()

with st.sidebar:
    st.selectbox(
        "Reference year", all_years, index=all_years.index(DETAIL_YEARS[-1]),
        key="year",
        help="2016-2019 from the Census of Manufacture. 2020 from the 2021 Economic "
             "Census, which has prefecture totals but no industry detail.")
    st.caption("Value added per worker, million yen, nominal. "
               "Source: METI Census of Manufacture and 2021 Economic Census via e-Stat.")

pages = [
    st.Page("views/overview.py", title="Overview", icon=":material/leaderboard:", default=True),
    st.Page("views/benchmark.py", title="Prefecture benchmark", icon=":material/location_on:"),
    st.Page("views/diagnosis.py", title="Diagnosis", icon=":material/scatter_plot:"),
    st.Page("views/industry.py", title="Industry context", icon=":material/precision_manufacturing:"),
    st.Page("views/notes.py", title="Notes", icon=":material/info:"),
]
st.navigation(pages).run()
