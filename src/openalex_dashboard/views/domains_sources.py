from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st


def render_domains_sources_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    works = filtered.get("works", pd.DataFrame()).copy()
    topics = filtered.get("topics_long", pd.DataFrame()).copy()

    st.subheader("Domains & sources")
    if works.empty:
        st.info("No publications match the current filters.")
        return

    col1, col2 = st.columns(2)
    with col1:
        if not topics.empty and "domain_name" in topics.columns:
            domain = topics.dropna(subset=["domain_name"]).groupby("domain_name", as_index=False).agg(works_count=("work_id", "nunique"))
            domain = domain.sort_values("works_count", ascending=False).head(15)
            if not domain.empty:
                fig = px.bar(domain, x="works_count", y="domain_name", orientation="h")
                fig.update_layout(title="OpenAlex domains", xaxis_title="Publications", yaxis_title="", margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not topics.empty and "subfield_name" in topics.columns:
            subfield = topics.dropna(subset=["subfield_name"]).groupby("subfield_name", as_index=False).agg(works_count=("work_id", "nunique"))
            subfield = subfield.sort_values("works_count", ascending=False).head(15)
            if not subfield.empty:
                fig = px.bar(subfield, x="works_count", y="subfield_name", orientation="h")
                fig.update_layout(title="OpenAlex subfields", xaxis_title="Publications", yaxis_title="", margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

    if "source_name" in works.columns:
        sources = works.dropna(subset=["source_name"]).groupby(["source_name", "source_type"], as_index=False, dropna=False).agg(
            works_count=("work_id", "nunique"), total_citations=("cited_by_count", "sum")
        )
        sources = sources.sort_values("works_count", ascending=False).head(30)
        st.markdown("### Top sources")
        st.dataframe(sources, use_container_width=True, hide_index=True)
