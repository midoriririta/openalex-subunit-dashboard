from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import streamlit as st


def _join_unique(values: pd.Series, limit: int = 12) -> str:
    clean: list[str] = []
    for value in values.dropna().astype(str):
        value = value.strip()
        if value and value.lower() != "nan" and value not in clean:
            clean.append(value)
    if len(clean) > limit:
        return "; ".join(clean[:limit]) + f"; +{len(clean) - limit} more"
    return "; ".join(clean)


def _ordered_confidence_join(values: pd.Series) -> str:
    order = {"high": 0, "medium": 1, "low": 2}
    clean = []
    for value in values.dropna().astype(str):
        value = value.strip().lower()
        if value and value not in clean:
            clean.append(value)
    clean = sorted(clean, key=lambda x: (order.get(x, 99), x))
    return "; ".join(clean)


def _add_roster_summary(works: pd.DataFrame, roster_works: pd.DataFrame) -> pd.DataFrame:
    if roster_works.empty or "work_id" not in roster_works.columns:
        return works

    agg_spec: dict[str, tuple[str, Any]] = {}
    if "paper_confidence" in roster_works.columns:
        agg_spec["paper_confidence"] = ("paper_confidence", _ordered_confidence_join)
    if "paper_confidence_score" in roster_works.columns:
        agg_spec["paper_confidence_score_min"] = ("paper_confidence_score", "min")
        agg_spec["paper_confidence_score_max"] = ("paper_confidence_score", "max")
    if "paper_confidence_reasons" in roster_works.columns:
        agg_spec["paper_confidence_reasons"] = ("paper_confidence_reasons", lambda s: _join_unique(s, limit=6))
    if "staff_name" in roster_works.columns:
        agg_spec["linked_staff"] = ("staff_name", lambda s: _join_unique(s))

    if not agg_spec:
        return works

    summary = roster_works.groupby("work_id", as_index=False).agg(**agg_spec)
    return works.merge(summary, on="work_id", how="left")


def _add_topic_keyword_summary(
    works: pd.DataFrame,
    topics_long: pd.DataFrame,
    keywords_long: pd.DataFrame,
) -> pd.DataFrame:
    if not topics_long.empty and "work_id" in topics_long.columns:
        topic_cols = [c for c in ["topic_name", "subfield_name", "field_name", "domain_name"] if c in topics_long.columns]
        if topic_cols:
            topic_summary = topics_long.groupby("work_id", as_index=False).agg(
                openalex_topics=("topic_name", lambda s: _join_unique(s, limit=8)) if "topic_name" in topic_cols else (topic_cols[0], lambda s: _join_unique(s, limit=8)),
                openalex_subfields=("subfield_name", lambda s: _join_unique(s, limit=6)) if "subfield_name" in topic_cols else (topic_cols[0], lambda s: ""),
            )
            works = works.merge(topic_summary, on="work_id", how="left")

    if not keywords_long.empty and "work_id" in keywords_long.columns and "keyword_name" in keywords_long.columns:
        keyword_summary = keywords_long.groupby("work_id", as_index=False).agg(
            openalex_keywords=("keyword_name", lambda s: _join_unique(s, limit=8))
        )
        works = works.merge(keyword_summary, on="work_id", how="left")

    return works


def _add_funding_summary(works: pd.DataFrame, funding_long: pd.DataFrame) -> pd.DataFrame:
    # Newer caches already have compact funding columns on works. This fallback
    # keeps the explorer useful if a cache has funding_long but not those columns.
    if funding_long.empty or "work_id" not in funding_long.columns:
        return works

    agg_parts: dict[str, tuple[str, Any]] = {}
    if "funder_name" in funding_long.columns and "funder_names" not in works.columns:
        agg_parts["funder_names"] = ("funder_name", lambda s: _join_unique(s, limit=10))
    if "award_id" in funding_long.columns and "award_ids" not in works.columns:
        agg_parts["award_ids"] = ("award_id", lambda s: _join_unique(s, limit=10))
    if not agg_parts:
        return works

    funding_summary = funding_long.groupby("work_id", as_index=False).agg(**agg_parts)
    return works.merge(funding_summary, on="work_id", how="left")


def render_explorer_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    works = filtered["works"].copy()
    roster_works = filtered.get("roster_works", pd.DataFrame()).copy()
    topics_long = filtered.get("topics_long", pd.DataFrame()).copy()
    keywords_long = filtered.get("keywords_long", pd.DataFrame()).copy()
    funding_long = filtered.get("funding_long", pd.DataFrame()).copy()

    st.subheader("Publications explorer")

    if works.empty:
        st.info("No publications match the current filters.")
        return

    if "doi" in works.columns:
        works["doi_url"] = works["doi"].apply(
            lambda value: f"https://doi.org/{value}" if pd.notna(value) and str(value).strip() else None
        )

    works = _add_roster_summary(works, roster_works)
    works = _add_topic_keyword_summary(works, topics_long, keywords_long)
    works = _add_funding_summary(works, funding_long)

    with st.expander("Funding metadata note", expanded=False):
        st.write(
            "Funding columns are populated from OpenAlex funders/awards metadata when available. "
            "Coverage is incomplete because not every publication has funder or grant data in OpenAlex. "
            "If these columns are empty after replacing the code, rebuild the OpenAlex cache once."
        )

    columns = [
        col
        for col in [
            "title",
            "publication_year",
            "publication_date",
            "source_name",
            "source_type",
            "work_type",
            "cited_by_count",
            "is_oa",
            "oa_status",
            "paper_confidence",
            "paper_confidence_score_min",
            "paper_confidence_score_max",
            "paper_confidence_reasons",
            "linked_staff",
            "openalex_topics",
            "openalex_keywords",
            "funder_names",
            "award_ids",
            "doi",
            "doi_url",
            "work_id",
        ]
        if col in works.columns
    ]

    sort_options = [col for col in ["publication_year", "cited_by_count", "source_name", "title"] if col in works.columns]
    sort_col = st.selectbox("Sort table by", options=sort_options, index=1 if "cited_by_count" in sort_options else 0)
    ascending = st.checkbox("Sort ascending", value=False)
    local_search_text = st.text_input(
        "Search visible table",
        value="",
        placeholder="Optional extra search within the already-filtered table",
    )

    if local_search_text:
        mask = pd.Series(False, index=works.index)
        for col in columns:
            mask = mask | works[col].fillna("").astype(str).str.contains(local_search_text, case=False, na=False)
        works = works[mask]

    if sort_col in works.columns:
        works = works.sort_values(sort_col, ascending=ascending)

    st.caption(f"Showing {works['work_id'].nunique():,} unique publications after all filters.")
    st.dataframe(works[columns], use_container_width=True, hide_index=True)
