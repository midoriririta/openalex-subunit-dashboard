from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st


def render_data_quality_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    people = bundle.get("people", pd.DataFrame()).copy()
    roster_works = filtered.get("roster_works", pd.DataFrame()).copy()
    candidates = bundle.get("author_candidates", pd.DataFrame()).copy()
    works = filtered.get("works", pd.DataFrame()).copy()

    st.subheader("Data quality")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("People in roster", f"{len(people):,}")
    with col2:
        st.metric("Candidate author rows", f"{len(candidates):,}")
    with col3:
        st.metric("Filtered roster-work links", f"{len(roster_works):,}")

    if not roster_works.empty and "paper_confidence" in roster_works.columns:
        conf = roster_works.groupby("paper_confidence", as_index=False).agg(links=("work_id", "size"), works=("work_id", "nunique"))
        fig = px.bar(conf, x="paper_confidence", y="works", hover_data=["links"])
        fig.update_layout(title="Paper confidence after current filters", xaxis_title="Confidence", yaxis_title="Unique works", margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    if not candidates.empty:
        st.markdown("### Author candidate audit")
        cols = [c for c in ["staff_name", "candidate_rank", "selected_for_fetch", "author_display_name", "author_works_count", "author_match_score", "author_match_confidence", "author_match_reasons", "openalex_author_id_full"] if c in candidates.columns]
        st.dataframe(candidates[cols], use_container_width=True, hide_index=True)

    missing_cols = [c for c in ["keywords_json", "funders_json", "awards_json", "funder_names", "award_ids"] if c not in works.columns]
    if missing_cols:
        st.warning("The current cache is missing newer topic/funding columns: " + ", ".join(missing_cols) + ". Rebuild the cache with the GitHub Action.")
