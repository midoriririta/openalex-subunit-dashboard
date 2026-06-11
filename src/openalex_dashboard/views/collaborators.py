from __future__ import annotations

import json
from typing import Any, Dict

import pandas as pd
import plotly.express as px
import pycountry
import streamlit as st


def _load_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if x]
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(value)
        return [str(x) for x in parsed if x]
    except Exception:
        return []


def _country_name(code: str) -> str:
    try:
        country = pycountry.countries.get(alpha_2=code)
        return country.name if country else code
    except Exception:
        return code


def render_collaborators_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    authorships = filtered.get("authorships", pd.DataFrame()).copy()
    works = filtered.get("works", pd.DataFrame()).copy()

    st.subheader("Collaborators")
    if authorships.empty or works.empty:
        st.info("No collaborator data match the current filters.")
        return

    external = authorships.copy()
    if "is_roster_person" in external.columns:
        external = external[~external["is_roster_person"].fillna(False)]

    st.metric("External co-authors", external["author_id_short"].nunique() if "author_id_short" in external.columns else len(external))

    if "author_name" in external.columns:
        top_authors = external.dropna(subset=["author_name"]).groupby("author_name", as_index=False).agg(
            shared_publications=("work_id", "nunique")
        ).sort_values("shared_publications", ascending=False).head(30)
        st.markdown("### Top external co-authors")
        st.dataframe(top_authors, use_container_width=True, hide_index=True)

    if "country_codes_json" in external.columns:
        countries = external[["work_id", "country_codes_json"]].copy()
        countries["country_code"] = countries["country_codes_json"].apply(_load_json_list)
        countries = countries.explode("country_code")
        countries = countries[countries["country_code"].notna() & (countries["country_code"] != "")]
        if not countries.empty:
            country_counts = countries.groupby("country_code", as_index=False).agg(works_count=("work_id", "nunique"))
            country_counts["country_name"] = country_counts["country_code"].map(_country_name)
            country_counts = country_counts.sort_values("works_count", ascending=False).head(30)
            fig = px.bar(country_counts, x="works_count", y="country_name", orientation="h")
            fig.update_layout(title="Top collaborator countries", xaxis_title="Publications", yaxis_title="", margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    if "institution_names_json" in external.columns:
        inst = external[["work_id", "institution_names_json"]].copy()
        inst["institution_name"] = inst["institution_names_json"].apply(_load_json_list)
        inst = inst.explode("institution_name")
        inst = inst[inst["institution_name"].notna() & (inst["institution_name"] != "")]
        if not inst.empty:
            inst_counts = inst.groupby("institution_name", as_index=False).agg(works_count=("work_id", "nunique"))
            inst_counts = inst_counts.sort_values("works_count", ascending=False).head(30)
            st.markdown("### Top collaborator institutions")
            st.dataframe(inst_counts, use_container_width=True, hide_index=True)
