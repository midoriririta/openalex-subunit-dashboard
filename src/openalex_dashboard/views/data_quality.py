from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st


def _format_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


def _confidence_summary(roster_works: pd.DataFrame) -> pd.DataFrame:
    if roster_works.empty or "paper_confidence" not in roster_works.columns:
        return pd.DataFrame()
    out = (
        roster_works.assign(paper_confidence=roster_works["paper_confidence"].fillna("Missing").astype(str).str.lower())
        .groupby("paper_confidence", as_index=False)
        .agg(links=("work_id", "size"), works=("work_id", "nunique"))
    )
    order = {"high": 0, "medium": 1, "low": 2, "missing": 3}
    out["_order"] = out["paper_confidence"].map(order).fillna(99)
    return out.sort_values(["_order", "paper_confidence"]).drop(columns="_order")


def _render_confidence_chart(df: pd.DataFrame, title: str) -> None:
    if df.empty:
        st.info(f"No paper-level confidence data available for {title.lower()}.")
        return
    fig = px.bar(df, x="paper_confidence", y="works", hover_data=["links"], text="works")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        title=title,
        xaxis_title="Paper confidence",
        yaxis_title="Unique works",
        margin=dict(l=0, r=0, t=45, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_data_quality_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    people = bundle.get("people", pd.DataFrame()).copy()
    full_roster_works = bundle.get("roster_works", pd.DataFrame()).copy()
    roster_works = filtered.get("roster_works", pd.DataFrame()).copy()
    candidates = bundle.get("author_candidates", pd.DataFrame()).copy()
    works = filtered.get("works", pd.DataFrame()).copy()
    authorships = filtered.get("authorships", pd.DataFrame()).copy()
    institutions = bundle.get("institutions", pd.DataFrame()).copy()
    topics_long = filtered.get("topics_long", pd.DataFrame()).copy()
    keywords_long = filtered.get("keywords_long", pd.DataFrame()).copy()
    funding_long = filtered.get("funding_long", pd.DataFrame()).copy()

    st.subheader("Data quality")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("People in roster", _format_int(len(people)))
    col2.metric("Candidate author rows", _format_int(len(candidates)))
    col3.metric("Filtered roster-work links", _format_int(len(roster_works)))
    col4.metric("Filtered works", _format_int(works["work_id"].nunique() if "work_id" in works.columns else len(works)))

    st.markdown("### Paper-level confidence")
    st.caption(
        "The left chart uses the complete cached roster-work table before the sidebar confidence filter. "
        "The right chart shows the currently filtered view. This makes medium/low-confidence papers visible for audit even when the default dashboard view keeps only high-confidence papers."
    )
    left, right = st.columns(2)
    with left:
        _render_confidence_chart(_confidence_summary(full_roster_works), "Full cached confidence distribution")
    with right:
        _render_confidence_chart(_confidence_summary(roster_works), "Confidence after current filters")

    if not candidates.empty:
        st.markdown("### Author candidate audit")
        cols = [
            c
            for c in [
                "staff_name",
                "candidate_rank",
                "selected_for_fetch",
                "author_display_name",
                "author_works_count",
                "author_match_score",
                "author_match_confidence",
                "author_match_reasons",
                "openalex_author_id_full",
            ]
            if c in candidates.columns
        ]
        st.dataframe(candidates[cols], use_container_width=True, hide_index=True)

    st.markdown("### Coverage checks")
    coverage = pd.DataFrame(
        {
            "table": [
                "people",
                "works",
                "authorships",
                "institutions",
                "topics_long",
                "keywords_long",
                "funding_long",
                "roster_works",
            ],
            "rows": [
                len(people),
                len(works),
                len(authorships),
                len(institutions),
                len(topics_long),
                len(keywords_long),
                len(funding_long),
                len(roster_works),
            ],
        }
    )
    st.dataframe(coverage, use_container_width=True, hide_index=True)

    if "publication_year" in works.columns and len(works):
        st.write(f"Missing publication_year in filtered works: {100 * works['publication_year'].isna().mean():.1f}%")
    if "source_name" in works.columns and len(works):
        st.write(f"Missing source_name in filtered works: {100 * works['source_name'].isna().mean():.1f}%")
    if "topics_json" in works.columns and len(works):
        st.write(f"Missing topics_json in filtered works: {100 * works['topics_json'].isna().mean():.1f}%")

    missing_cols = [
        c
        for c in ["keywords_json", "funders_json", "awards_json", "funder_names", "award_ids"]
        if c not in works.columns
    ]
    if missing_cols:
        st.warning(
            "The current cache is missing newer topic/funding columns: "
            + ", ".join(missing_cols)
            + ". Rebuild the cache with the GitHub Action."
        )
