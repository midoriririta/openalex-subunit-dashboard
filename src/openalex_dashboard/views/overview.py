from __future__ import annotations

from html import escape
from typing import Any, Dict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


OA_STATUS_STYLES = {
    "green": ("Free copy in a repository", "Green", "#287F81"),
    "gold": ("Fully open-access journal", "Gold", "#284F70"),
    "diamond": ("Open journal, no publishing fee", "Diamond", "#557A64"),
    "hybrid": ("Open article in a subscription journal", "Hybrid", "#7C92AF"),
    "bronze": ("Free on publisher website", "Bronze", "#B18B50"),
    "closed": ("No free copy recorded", "Closed", "#A4ABB2"),
    "unknown": ("Status not recorded", "Unknown", "#D1D6DA"),
}


def _render_open_access_panel(works: pd.DataFrame) -> None:
    oa = works[["work_id", "oa_status"]].copy()
    status = oa["oa_status"].astype("string").str.strip().str.lower()
    oa["oa_status"] = status.where(status.isin(OA_STATUS_STYLES), "unknown")
    counts = oa.groupby("oa_status")["work_id"].nunique()
    statuses = [status for status in OA_STATUS_STYLES if counts.get(status, 0) > 0]
    total = int(counts.sum())
    if not total:
        return

    labels = [OA_STATUS_STYLES[status][0] for status in statuses]
    terms = [OA_STATUS_STYLES[status][1] for status in statuses]
    colors = [OA_STATUS_STYLES[status][2] for status in statuses]
    values = [int(counts[status]) for status in statuses]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            customdata=terms,
            marker=dict(colors=colors, line=dict(width=0)),
            hole=0.7,
            sort=False,
            direction="clockwise",
            textinfo="none",
            hovertemplate="%{label} (%{customdata})<br>%{value:,} publications · %{percent:.1%}<extra></extra>",
        )
    )
    fig.update_layout(
        showlegend=False,
        height=220,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(
            x=0.5, y=0.5, showarrow=False,
            text=f"<b>{total:,}</b><br><span style='font-size:11px'>publications</span>",
            font=dict(size=22),
        )],
    )

    st.markdown("##### Open access status")
    with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center", gap="small"):
        chart_col = st.container(width=180)
        legend_col = st.container(width=380)
    with chart_col:
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    with legend_col:
        rows = []
        for status, count in zip(statuses, values):
            label, term, color = OA_STATUS_STYLES[status]
            rows.append(
                f'<div class="oa-status-row" role="listitem">'
                f'<span class="oa-status-swatch" style="background:{color}" aria-hidden="true"></span>'
                f'<span class="oa-status-label">{escape(label)}<small>{escape(term)}</small></span>'
                f'<span class="oa-status-value">{count / total:.1%}<small>{count:,} publications</small></span>'
                '</div>'
            )
        st.html(
            """<style>
            .oa-status-legend { font-size:13px; line-height:1.4; }
            .oa-status-row { display:grid; grid-template-columns:9px minmax(0,1fr) 106px;
                gap:9px; align-items:start; padding:10px 0; border-bottom:1px solid rgba(128,140,153,.25); }
            .oa-status-row:last-child { border-bottom:0; }
            .oa-status-swatch { width:9px; height:9px; border-radius:2px; margin-top:5px; }
            .oa-status-label { font-weight:500; overflow-wrap:anywhere; }
            .oa-status-value { font-weight:500; text-align:right; font-variant-numeric:tabular-nums; }
            .oa-status-legend small { display:block; opacity:.74; font-size:11px; font-weight:400;
                margin-top:3px; }
            </style><div class="oa-status-legend" role="list" aria-label="Open access categories">"""
            + "".join(rows) + "</div>"
        )


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
            _render_open_access_panel(works)
    with col_b:
        if "work_type" in works.columns:
            wt = works.fillna({"work_type": "unknown"}).groupby("work_type", as_index=False).agg(works_count=("work_id", "nunique"))
            wt = wt.sort_values("works_count", ascending=False).head(12)
            if not wt.empty:
                fig = px.bar(wt, x="works_count", y="work_type", orientation="h")
                fig.update_layout(title="Publication types", xaxis_title="Publications", yaxis_title="", margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
