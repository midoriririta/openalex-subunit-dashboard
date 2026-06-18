from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Dict, Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pycountry
import streamlit as st

from src.openalex_dashboard.data import safe_json_loads

try:
    import networkx as nx
except Exception:  # pragma: no cover
    nx = None

# The NDPH cache can be large. These caps keep the collaborator tab stable while
# still showing the highest-signal part of the collaboration structure.
MAX_EXTERNAL_NETWORK_WORKS = 12000
MAX_EXTERNAL_AUTHORS_PER_WORK = 12
MAX_ROSTER_AUTHORS_PER_WORK = 8
MAX_EXTERNAL_NODES = 35
MAX_EXTERNAL_EDGES = 140
MAX_INTERNAL_NETWORK_WORKS = 18000
MAX_INTERNAL_EDGES = 80
MAX_INTERNAL_PAIRS_TABLE = 50


def format_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


def _plotly_chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch")


def _dataframe(df: pd.DataFrame, **kwargs) -> None:
    st.dataframe(df, width="stretch", hide_index=True, **kwargs)


def alpha2_to_country(code: Any):
    if not code or pd.isna(code):
        return None
    try:
        return pycountry.countries.get(alpha_2=str(code).upper())
    except Exception:
        return None


def alpha2_to_alpha3(code: Any):
    country = alpha2_to_country(code)
    return getattr(country, "alpha_3", None) if country else None


def alpha2_to_name(code: Any) -> str | None:
    country = alpha2_to_country(code)
    return getattr(country, "name", None) if country else None


def _external_authorships(authorships: pd.DataFrame) -> pd.DataFrame:
    if authorships.empty:
        return authorships.copy()
    external = authorships.copy()
    if "is_roster_person" in external.columns:
        external = external[~external["is_roster_person"].fillna(False)].copy()
    return external


def _unique_clean_values(values: Iterable[Any], limit: int | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None or pd.isna(value):
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if limit is not None and len(out) >= limit:
            break
    return out


def _list_from_json(value: Any, limit: int | None = None) -> list[str]:
    return _unique_clean_values(safe_json_loads(value), limit=limit)


def _country_summary(external: pd.DataFrame) -> pd.DataFrame:
    if external.empty or "work_id" not in external.columns or "country_codes_json" not in external.columns:
        return pd.DataFrame()

    rows_counter: Counter[str] = Counter()
    work_sets: dict[str, set[str]] = defaultdict(set)
    author_sets: dict[str, set[str]] = defaultdict(set)

    author_col = "author_id_short" if "author_id_short" in external.columns else None
    cols = ["work_id", "country_codes_json"] + ([author_col] if author_col else [])
    for row in external[cols].itertuples(index=False, name=None):
        work_id = str(row[0]) if row[0] is not None else ""
        countries = _list_from_json(row[1])
        author_id = str(row[2]) if author_col and len(row) > 2 and row[2] is not None else ""
        for code in countries:
            code = str(code).upper().strip()
            if not code:
                continue
            rows_counter[code] += 1
            if work_id:
                work_sets[code].add(work_id)
            if author_id:
                author_sets[code].add(author_id)

    if not rows_counter:
        return pd.DataFrame()

    records = []
    for code, row_count in rows_counter.items():
        records.append(
            {
                "country_code": code,
                "external_authorship_rows": row_count,
                "collaborator_works": len(work_sets.get(code, set())),
                "unique_external_authors": len(author_sets.get(code, set())),
            }
        )
    country_summary = pd.DataFrame(records).sort_values("collaborator_works", ascending=False)
    country_summary["country_name"] = country_summary["country_code"].apply(alpha2_to_name)
    country_summary["country_name"] = country_summary["country_name"].fillna(country_summary["country_code"])
    country_summary["iso_alpha"] = country_summary["country_code"].apply(alpha2_to_alpha3)
    return country_summary


def _render_country_map(country_summary: pd.DataFrame) -> None:
    st.subheader("Collaborator works by country")
    if country_summary.empty:
        st.info("No external collaborator country data for the current filters.")
        return

    map_df = country_summary[country_summary["iso_alpha"].notna()].copy()
    if map_df.empty:
        st.info("No mappable country codes after conversion.")
        _dataframe(country_summary.head(25))
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Collaborator countries", format_int(map_df["iso_alpha"].nunique()))
    c2.metric("Collaborator works", format_int(map_df["collaborator_works"].sum()))
    c3.metric("Unique external authors", format_int(map_df["unique_external_authors"].sum()))

    fig = px.choropleth(
        map_df,
        locations="iso_alpha",
        color="collaborator_works",
        hover_name="country_name",
        custom_data=[
            "country_name",
            "country_code",
            "collaborator_works",
            "unique_external_authors",
            "external_authorship_rows",
        ],
        color_continuous_scale="YlGnBu",
        projection="natural earth",
    )
    fig.update_traces(
        marker_line_color="rgba(255,255,255,0.72)",
        marker_line_width=0.45,
        hovertemplate=(
            "%{customdata[0]} (%{customdata[1]})<br>"
            "Collaborator works: %{customdata[2]:,}<br>"
            "Unique external authors: %{customdata[3]:,}<br>"
            "External authorship rows: %{customdata[4]:,}"
            "<extra></extra>"
        ),
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=True,
        coastlinecolor="rgba(84,105,120,0.45)",
        showcountries=True,
        countrycolor="rgba(255,255,255,0.7)",
        showland=True,
        landcolor="rgba(244,247,250,1)",
        showocean=True,
        oceancolor="rgba(228,239,248,1)",
        bgcolor="rgba(0,0,0,0)",
        lataxis_showgrid=False,
        lonaxis_showgrid=False,
    )
    fig.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=12, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(title="Works", thickness=14, len=0.62, y=0.48, outlinewidth=0),
    )
    _plotly_chart(fig)
    st.caption("Countries are counted from external co-author affiliation country codes in the currently filtered publication set.")

    left, right = st.columns([1.15, 1])
    with left:
        top_countries = map_df.head(15).sort_values("collaborator_works", ascending=True)
        fig_bar = px.bar(
            top_countries,
            x="collaborator_works",
            y="country_name",
            orientation="h",
            text="collaborator_works",
            labels={"country_name": "Country", "collaborator_works": "Collaborator works"},
            title="Top collaborator countries",
        )
        fig_bar.update_traces(textposition="outside", cliponaxis=False)
        fig_bar.update_layout(
            height=430,
            margin=dict(l=0, r=20, t=48, b=0),
            yaxis=dict(title=None),
            xaxis=dict(title="Collaborator works", rangemode="tozero"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        _plotly_chart(fig_bar)

    with right:
        show_cols = ["country_name", "country_code", "collaborator_works", "unique_external_authors", "external_authorship_rows"]
        _dataframe(
            country_summary[show_cols].head(25),
            column_config={
                "country_name": "Country",
                "country_code": "Code",
                "collaborator_works": "Works",
                "unique_external_authors": "External authors",
                "external_authorship_rows": "Authorship rows",
            },
        )


def _top_external_institutions(external: pd.DataFrame, limit: int = 25) -> pd.DataFrame:
    if external.empty or "work_id" not in external.columns or "institution_names_json" not in external.columns:
        return pd.DataFrame()

    row_counter: Counter[str] = Counter()
    work_sets: dict[str, set[str]] = defaultdict(set)
    author_sets: dict[str, set[str]] = defaultdict(set)
    author_col = "author_id_short" if "author_id_short" in external.columns else None
    cols = ["work_id", "institution_names_json"] + ([author_col] if author_col else [])
    for row in external[cols].itertuples(index=False, name=None):
        work_id = str(row[0]) if row[0] is not None else ""
        institutions = _list_from_json(row[1], limit=20)
        author_id = str(row[2]) if author_col and len(row) > 2 and row[2] is not None else ""
        for inst in institutions:
            row_counter[inst] += 1
            if work_id:
                work_sets[inst].add(work_id)
            if author_id:
                author_sets[inst].add(author_id)

    if not row_counter:
        return pd.DataFrame()

    records = [
        {
            "institution_name_exploded": inst,
            "external_authorship_rows": rows,
            "collaborator_works": len(work_sets.get(inst, set())),
            "unique_external_authors": len(author_sets.get(inst, set())),
        }
        for inst, rows in row_counter.items()
    ]
    return pd.DataFrame(records).sort_values("collaborator_works", ascending=False).head(limit)


def _clean_node_name(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def _add_node_id(df: pd.DataFrame, prefer_roster_name: bool) -> pd.DataFrame:
    out = df.copy()
    fallback = pd.Series([None] * len(out), index=out.index, dtype="object")
    if "author_id_short" in out.columns:
        fallback = out["author_id_short"]
    if prefer_roster_name and "roster_person_name" in out.columns:
        node_id = out["roster_person_name"]
        if "author_name" in out.columns:
            node_id = node_id.fillna(out["author_name"])
        node_id = node_id.fillna(fallback)
    else:
        if "author_name" in out.columns:
            node_id = out["author_name"].fillna(fallback)
        else:
            node_id = fallback
    out["node_id"] = node_id.apply(_clean_node_name)
    return out[out["node_id"].notna()].copy()


def _node_totals(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame(columns=["node", "total_shared_works"])
    degree_weight = pd.concat(
        [
            edges[["source", "shared_works"]].rename(columns={"source": "node"}),
            edges[["target", "shared_works"]].rename(columns={"target": "node"}),
        ],
        ignore_index=True,
    )
    return degree_weight.groupby("node", as_index=False).agg(total_shared_works=("shared_works", "sum"))


def _limit_work_ids_for_network(authorships: pd.DataFrame, max_works: int) -> tuple[set[str], bool]:
    if "work_id" not in authorships.columns:
        return set(), False
    work_order = authorships[["work_id"]].drop_duplicates().copy()
    if "publication_year" in authorships.columns:
        year_lookup = authorships[["work_id", "publication_year"]].drop_duplicates("work_id")
        work_order = work_order.merge(year_lookup, on="work_id", how="left")
        work_order["publication_year"] = pd.to_numeric(work_order["publication_year"], errors="coerce").fillna(-1)
        work_order = work_order.sort_values(["publication_year", "work_id"], ascending=[False, True])
    total = len(work_order)
    if total > max_works:
        work_order = work_order.head(max_works)
    return set(work_order["work_id"].astype(str)), total > max_works


def _build_collaboration_edges(
    authorships: pd.DataFrame,
    max_external_nodes: int = MAX_EXTERNAL_NODES,
    max_edges: int = MAX_EXTERNAL_EDGES,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    required = {"work_id", "author_id_short", "author_name", "is_roster_person"}
    if authorships.empty or not required.issubset(authorships.columns):
        return pd.DataFrame(), pd.DataFrame(), False

    work_ids, capped = _limit_work_ids_for_network(authorships, MAX_EXTERNAL_NETWORK_WORKS)
    if not work_ids:
        return pd.DataFrame(), pd.DataFrame(), capped
    auth = authorships[authorships["work_id"].astype(str).isin(work_ids)].copy()

    roster = auth[auth["is_roster_person"].fillna(False)].copy()
    external = auth[~auth["is_roster_person"].fillna(False)].copy()
    if roster.empty or external.empty:
        return pd.DataFrame(), pd.DataFrame(), capped

    roster = _add_node_id(roster, prefer_roster_name=True)[["work_id", "node_id"]].drop_duplicates()
    external = _add_node_id(external, prefer_roster_name=False)[["work_id", "node_id"]].drop_duplicates()
    if roster.empty or external.empty:
        return pd.DataFrame(), pd.DataFrame(), capped

    roster_by_work = roster.groupby("work_id")["node_id"].apply(lambda s: _unique_clean_values(s, limit=MAX_ROSTER_AUTHORS_PER_WORK))
    external_by_work = external.groupby("work_id")["node_id"].apply(lambda s: _unique_clean_values(s, limit=MAX_EXTERNAL_AUTHORS_PER_WORK))

    edge_counts: Counter[tuple[str, str]] = Counter()
    external_totals: Counter[str] = Counter()
    for work_id, sources in roster_by_work.items():
        targets = external_by_work.get(work_id)
        if not targets:
            continue
        for source in sources:
            for target in targets:
                if source and target and source != target:
                    edge_counts[(source, target)] += 1
                    external_totals[target] += 1

    if not edge_counts:
        return pd.DataFrame(), pd.DataFrame(), capped

    top_external = {node for node, _ in external_totals.most_common(max_external_nodes)}
    records = [
        {"source": source, "target": target, "shared_works": count}
        for (source, target), count in edge_counts.items()
        if target in top_external
    ]
    if not records:
        return pd.DataFrame(), pd.DataFrame(), capped

    edges = pd.DataFrame(records).sort_values("shared_works", ascending=False).head(max_edges)
    nodes = pd.DataFrame({"node": sorted(set(edges["source"]).union(edges["target"]))})
    roster_nodes = set(edges["source"])
    nodes["kind"] = nodes["node"].apply(lambda x: "Roster" if x in roster_nodes else "External collaborator")
    nodes = nodes.merge(_node_totals(edges), on="node", how="left")
    nodes["total_shared_works"] = nodes["total_shared_works"].fillna(0)
    return nodes, edges, capped


def _internal_roster_authorships(authorships: pd.DataFrame, max_works: int | None = None) -> tuple[pd.DataFrame, bool]:
    required = {"work_id", "is_roster_person"}
    if authorships.empty or not required.issubset(authorships.columns):
        return pd.DataFrame(), False
    auth = authorships
    capped = False
    if max_works is not None:
        work_ids, capped = _limit_work_ids_for_network(authorships, max_works)
        auth = authorships[authorships["work_id"].astype(str).isin(work_ids)].copy()
    roster = auth[auth["is_roster_person"].fillna(False)].copy()
    if roster.empty:
        return pd.DataFrame(), capped
    roster = _add_node_id(roster, prefer_roster_name=True)
    if roster.empty:
        return pd.DataFrame(), capped
    return roster[["work_id", "node_id"]].drop_duplicates(), capped


def _build_internal_collaboration_edges(
    authorships: pd.DataFrame,
    max_edges: int = MAX_INTERNAL_EDGES,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    roster, capped = _internal_roster_authorships(authorships, max_works=MAX_INTERNAL_NETWORK_WORKS)
    if roster.empty:
        return pd.DataFrame(), pd.DataFrame(), capped

    edge_counts: Counter[tuple[str, str]] = Counter()
    for _, group in roster.groupby("work_id"):
        staff_names = _unique_clean_values(group["node_id"], limit=MAX_ROSTER_AUTHORS_PER_WORK)
        if len(staff_names) < 2:
            continue
        for source, target in combinations(sorted(staff_names), 2):
            if source and target and source != target:
                edge_counts[(source, target)] += 1

    if not edge_counts:
        return pd.DataFrame(), pd.DataFrame(), capped

    edges = pd.DataFrame(
        [
            {"source": source, "target": target, "shared_works": count}
            for (source, target), count in edge_counts.items()
        ]
    ).sort_values(["shared_works", "source", "target"], ascending=[False, True, True])
    graph_edges = edges.head(max_edges).copy()
    nodes = pd.DataFrame({"node": sorted(set(graph_edges["source"]).union(graph_edges["target"]))})
    nodes["kind"] = "Internal staff"
    nodes = nodes.merge(_node_totals(graph_edges), on="node", how="left")
    nodes["total_shared_works"] = nodes["total_shared_works"].fillna(0)
    return nodes, edges, capped


def _build_internal_collaborator_ranking(authorships: pd.DataFrame) -> pd.DataFrame:
    roster, _ = _internal_roster_authorships(authorships, max_works=MAX_INTERNAL_NETWORK_WORKS)
    if roster.empty:
        return pd.DataFrame()

    collaborators_by_person: dict[str, set[str]] = defaultdict(set)
    for _, group in roster.groupby("work_id"):
        staff_names = set(_unique_clean_values(group["node_id"], limit=MAX_ROSTER_AUTHORS_PER_WORK))
        if len(staff_names) < 2:
            continue
        for person in staff_names:
            collaborators_by_person[person].update(staff_names - {person})

    if not collaborators_by_person:
        return pd.DataFrame()
    ranking = pd.DataFrame(
        [
            {"internal_staff_member": person, "unique_internal_collaborators": len(collaborators)}
            for person, collaborators in collaborators_by_person.items()
        ]
    )
    return ranking.sort_values(["unique_internal_collaborators", "internal_staff_member"], ascending=[False, True])


def _layout_network(nodes: pd.DataFrame, edges: pd.DataFrame, seed: int = 7) -> dict[str, tuple[float, float]]:
    if nx is not None:
        graph = nx.Graph()
        for _, row in nodes.iterrows():
            graph.add_node(row["node"], kind=row["kind"], weight=row["total_shared_works"])
        for _, row in edges.iterrows():
            graph.add_edge(row["source"], row["target"], weight=row["shared_works"])
        return nx.spring_layout(graph, seed=seed, k=0.9)

    import math

    ordered = nodes["node"].tolist()
    return {
        node: (
            math.cos(2 * math.pi * i / max(len(ordered), 1)),
            math.sin(2 * math.pi * i / max(len(ordered), 1)),
        )
        for i, node in enumerate(ordered)
    }


def _draw_network_figure(nodes: pd.DataFrame, edges: pd.DataFrame, title: str, height: int = 650, seed: int = 7) -> None:
    plot_edges = edges[edges["source"].isin(nodes["node"]) & edges["target"].isin(nodes["node"])].copy()
    if nodes.empty or plot_edges.empty:
        return
    pos = _layout_network(nodes, plot_edges, seed=seed)

    edge_x, edge_y = [], []
    for _, row in plot_edges.iterrows():
        x0, y0 = pos[row["source"]]
        x1, y1 = pos[row["target"]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(width=0.7, color="rgba(86, 105, 128, 0.28)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    for kind, group in nodes.groupby("kind"):
        xs = [pos[node][0] for node in group["node"]]
        ys = [pos[node][1] for node in group["node"]]
        shared = group["total_shared_works"].fillna(0).astype(float)
        sizes = 12 + shared.clip(upper=35)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers+text",
                text=group["node"],
                textposition="top center",
                customdata=shared,
                marker=dict(size=sizes, line=dict(width=1.2, color="white"), opacity=0.88),
                name=kind,
                hovertemplate=("%{text}<br>" f"Type: {kind}<br>" "Total shared works: %{customdata:,}" "<extra></extra>"),
            )
        )

    fig.update_layout(
        title=title,
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        margin=dict(l=10, r=10, t=50, b=10),
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    _plotly_chart(fig)


def _render_network(authorships: pd.DataFrame) -> None:
    st.subheader("External collaboration network")
    nodes, edges, capped = _build_collaboration_edges(authorships)
    if capped:
        st.caption(
            f"Network graph is capped to the most recent {MAX_EXTERNAL_NETWORK_WORKS:,} works and the strongest edges so the NDPH view stays responsive. Tables/maps above still use the full filtered set."
        )
    if nodes.empty or edges.empty:
        st.info("No external co-author network can be drawn for the current filters.")
        return
    _draw_network_figure(nodes=nodes, edges=edges, title="Roster staff connected to external co-authors", height=650, seed=7)


def _render_internal_network(authorships: pd.DataFrame) -> None:
    st.subheader("Internal staff collaboration network")
    nodes, edges, capped = _build_internal_collaboration_edges(authorships)
    if capped:
        st.caption(
            f"Internal network graph is capped to the most recent {MAX_INTERNAL_NETWORK_WORKS:,} works and strongest edges for stability."
        )
    if nodes.empty or edges.empty:
        st.info("No internal staff-to-staff collaboration network can be drawn for the current filters.")
        return

    graph_edges = edges.head(MAX_INTERNAL_EDGES).copy()
    graph_nodes = pd.DataFrame({"node": sorted(set(graph_edges["source"]).union(graph_edges["target"]))})
    graph_nodes["kind"] = "Internal staff"
    graph_nodes = graph_nodes.merge(_node_totals(graph_edges), on="node", how="left")
    graph_nodes["total_shared_works"] = graph_nodes["total_shared_works"].fillna(0)
    _draw_network_figure(nodes=graph_nodes, edges=graph_edges, title="Internal roster staff connected by shared works", height=620, seed=11)

    table_view = st.selectbox(
        "Internal collaboration ranking",
        options=["Top internal collaborator pairs", "Top internal collaborators"],
        index=0,
    )
    if table_view == "Top internal collaborator pairs":
        top_pairs = edges.head(MAX_INTERNAL_PAIRS_TABLE).rename(
            columns={"source": "staff_member_1", "target": "staff_member_2", "shared_works": "collaboration_count"}
        )
        _dataframe(
            top_pairs,
            column_config={
                "staff_member_1": "Internal staff member 1",
                "staff_member_2": "Internal staff member 2",
                "collaboration_count": "Shared works",
            },
        )
    else:
        ranking = _build_internal_collaborator_ranking(authorships)
        if ranking.empty:
            st.info("No person-level internal collaboration ranking can be drawn for the current filters.")
            return
        _dataframe(
            ranking.head(30),
            column_config={
                "internal_staff_member": "Internal staff member",
                "unique_internal_collaborators": "Unique internal collaborators",
            },
        )


def render_collaborators_tab(bundle: Dict[str, Any], filtered: Dict[str, Any]) -> None:
    authorships = filtered.get("authorships", pd.DataFrame())
    if authorships.empty:
        st.info("No collaborator data match the current filters.")
        return

    n_works = authorships["work_id"].nunique() if "work_id" in authorships.columns else 0
    n_rows = len(authorships)
    st.caption(f"Collaboration view based on {format_int(n_works)} filtered works and {format_int(n_rows)} authorship rows.")

    external = _external_authorships(authorships)
    country_summary = _country_summary(external)
    _render_country_map(country_summary)

    st.subheader("Top external institutions")
    top_insts = _top_external_institutions(external)
    if top_insts.empty:
        st.info("No external institution data for the current filters.")
    else:
        _dataframe(
            top_insts,
            column_config={
                "institution_name_exploded": "Institution",
                "external_authorship_rows": "Authorship rows",
                "collaborator_works": "Works",
                "unique_external_authors": "External authors",
            },
        )

    _render_network(authorships)
    _render_internal_network(authorships)
