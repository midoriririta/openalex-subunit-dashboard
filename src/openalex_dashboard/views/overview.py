from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st


def _safe_metric(label: str, value: Any) -> None:
    try:
        st.metric(label, f"{int(value):,}")
    except Exception:
        st.metric(label, str(value))


def render_overview_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    works = filtered.get("works", pd.DataFrame()).copy()
    roster_works = filtered.get("roster_works", pd.DataFrame()).copy()
    people = bundle.get("people", pd.DataFrame()).copy()

    st.subheader("Overview")
    if works.empty:
        st.info("No publications match the current filters.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _safe_metric("Publications", works["work_id"].nunique() if "work_id" in works.columns else len(works))
    with col2:
        _safe_metric("Citations", works.get("cited_by_count", pd.Series(dtype=float)).fillna(0).sum())
    with col3:
        _safe_metric("Linked staff", roster_works["staff_name"].nunique() if "staff_name" in roster_works.columns else people.shape[0])
    with col4:
        years = works.get("publication_year", pd.Series(dtype="Int64")).dropna()
        st.metric("Year range", f"{int(years.min())}–{int(years.max())}" if len(years) else "n/a")

    by_year = (
        works.dropna(subset=["publication_year"])
        .groupby("publication_year", as_index=False)
        .agg(works_count=("work_id", "nunique"), total_citations=("cited_by_count", "sum"))
        .sort_values("publication_year")
    )
    if not by_year.empty:
        fig = px.bar(by_year, x="publication_year", y="works_count", hover_data=["total_citations"])
        fig.update_layout(xaxis_title="Publication year", yaxis_title="Publications", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if "oa_status" in works.columns:
            oa = works.fillna({"oa_status": "unknown"}).groupby("oa_status", as_index=False).agg(works_count=("work_id", "nunique"))
            if not oa.empty:
                fig = px.pie(oa, names="oa_status", values="works_count", hole=0.45)
                fig.update_layout(title="Open access status", margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
    with col_b:
        if "work_type" in works.columns:
            wt = works.fillna({"work_type": "unknown"}).groupby("work_type", as_index=False).agg(works_count=("work_id", "nunique"))
            wt = wt.sort_values("works_count", ascending=False).head(12)
            if not wt.empty:
                fig = px.bar(wt, x="works_count", y="work_type", orientation="h")
                fig.update_layout(title="Publication types", xaxis_title="Publications", yaxis_title="", margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
