from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import streamlit as st


def _grouped_text(
    frame: pd.DataFrame, column: str, limit: int = 12, *, confidence: bool = False,
) -> pd.Series:
    # Clean each column once, rather than constructing and cleaning a Series
    # for every publication. Dicts retain the first-seen order of unique values.
    groups: dict[Any, dict[str, None]] = {
        work_id: {} for work_id in frame["work_id"].dropna().unique()
    }
    pairs = frame.loc[frame["work_id"].notna() & frame[column].notna(), ["work_id", column]].copy()
    pairs[column] = pairs[column].astype(str).str.strip()
    if confidence:
        pairs[column] = pairs[column].str.lower()
    valid = pairs[column].ne("")
    if not confidence:
        valid &= pairs[column].str.lower().ne("nan")
    for work_id, value in pairs.loc[valid].drop_duplicates().itertuples(index=False, name=None):
        groups[work_id][value] = None

    order = {"high": 0, "medium": 1, "low": 2}
    result = {}
    for work_id, values in groups.items():
        clean = list(values)
        if confidence:
            clean.sort(key=lambda value: (order.get(value, 99), value))
            result[work_id] = "; ".join(clean)
        else:
            result[work_id] = "; ".join(clean[:limit])
            if len(clean) > limit:
                result[work_id] += f"; +{len(clean) - limit} more"
    return pd.Series(result, name=column, dtype="str").rename_axis("work_id")


def _add_roster_summary(works: pd.DataFrame, roster_works: pd.DataFrame) -> pd.DataFrame:
    if roster_works.empty or "work_id" not in roster_works.columns:
        return works

    parts = {}
    if "paper_confidence" in roster_works.columns:
        parts["paper_confidence"] = _grouped_text(roster_works, "paper_confidence", confidence=True)
    if "paper_confidence_score" in roster_works.columns:
        scores = roster_works.groupby("work_id")["paper_confidence_score"].agg(["min", "max"])
        parts["paper_confidence_score_min"] = scores["min"]
        parts["paper_confidence_score_max"] = scores["max"]
    if "paper_confidence_reasons" in roster_works.columns:
        parts["paper_confidence_reasons"] = _grouped_text(roster_works, "paper_confidence_reasons", limit=6)
    if "staff_name" in roster_works.columns:
        parts["linked_staff"] = _grouped_text(roster_works, "staff_name")

    if not parts:
        return works

    summary = pd.DataFrame(parts).reset_index()
    return works.merge(summary, on="work_id", how="left")


def _add_topic_keyword_summary(
    works: pd.DataFrame,
    topics_long: pd.DataFrame,
    keywords_long: pd.DataFrame,
) -> pd.DataFrame:
    if not topics_long.empty and "work_id" in topics_long.columns:
        topic_cols = [c for c in ["topic_name", "subfield_name", "field_name", "domain_name"] if c in topics_long.columns]
        if topic_cols:
            topic_summary = pd.DataFrame({
                "openalex_topics": _grouped_text(topics_long, "topic_name" if "topic_name" in topic_cols else topic_cols[0], limit=8),
            })
            topic_summary["openalex_subfields"] = _grouped_text(topics_long, "subfield_name", limit=6) if "subfield_name" in topic_cols else ""
            topic_summary = topic_summary.reset_index()
            works = works.merge(topic_summary, on="work_id", how="left")

    if not keywords_long.empty and "work_id" in keywords_long.columns and "keyword_name" in keywords_long.columns:
        keyword_summary = _grouped_text(keywords_long, "keyword_name", limit=8).rename("openalex_keywords").reset_index()
        works = works.merge(keyword_summary, on="work_id", how="left")

    return works


def _add_funding_summary(works: pd.DataFrame, funding_long: pd.DataFrame) -> pd.DataFrame:
    # Newer caches already have compact funding columns on works. This fallback
    # keeps the explorer useful if a cache has funding_long but not those columns.
    if funding_long.empty or "work_id" not in funding_long.columns:
        return works

    parts = {}
    if "funder_name" in funding_long.columns and "funder_names" not in works.columns:
        parts["funder_names"] = _grouped_text(funding_long, "funder_name", limit=10)
    if "award_id" in funding_long.columns and "award_ids" not in works.columns:
        parts["award_ids"] = _grouped_text(funding_long, "award_id", limit=10)
    if not parts:
        return works

    funding_summary = pd.DataFrame(parts).reset_index()
    return works.merge(funding_summary, on="work_id", how="left")


def render_explorer_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    works = filtered["works"].copy()
    roster_works = filtered.get("roster_works", pd.DataFrame())
    topics_long = filtered.get("topics_long", pd.DataFrame())
    keywords_long = filtered.get("keywords_long", pd.DataFrame())
    funding_long = filtered.get("funding_long", pd.DataFrame())

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
