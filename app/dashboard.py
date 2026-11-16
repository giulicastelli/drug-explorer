"""Dashboard: which drugs treat this condition?

The user types a condition; the page shows the active ingredients whose FDA label
"Indications and usage" text mentions it (full-text search, GIN index on labels.tsv), in three views:
  Atlas            a map of the ingredients placed by the words of their labels (loader/atlas.py);
                   the search lights up the ingredients that match, a click opens one of them.
  Top ingredients  the ranking: bar chart, table, and the labels of one ingredient.
  About the data   what the search is and is not, how the atlas is made, where the data comes from.
The queries live in sql/queries.sql; the look in .streamlit/config.toml and docs/design_system.md.
Run inside docker compose: the database is reached by its service name, "db".
"""
import html
import os
import time
from pathlib import Path

import altair as alt
import pandas as pd
import psycopg
import streamlit as st

DB = dict(
    host=os.environ.get("DB_HOST", "db"),          # the service name, never localhost
    port=int(os.environ.get("DB_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
QUERIES_FILE = Path(__file__).parent / "sql" / "queries.sql"
PRODUCT_TYPES = {"All": "all", "Rx": "Rx", "OTC": "OTC"}
TYPE_WORDS = {"Rx": "prescription", "OTC": "over the counter"}
EXAMPLES = ["migraine", "epilepsy", "asthma", "hypertension", "acne", "insomnia"]
NO_CLASS = "not in label data"

# Design tokens (docs/design_system.md). Data colours: a validated data-visualisation palette, dark mode,
# first three slots, validated all-pairs (scatter) with its script. Ink and surfaces from the same file.
KIND_COLORS = {"Rx only": "#3987e5", "OTC only": "#d95926", "Rx and OTC": "#199e70", "other": "#898781"}
BAR_COLORS = {"Rx": "#3987e5", "OTC": "#d95926", "other": "#898781"}
INK, INK_2, MUTED = "#f0efec", "#c3c2b7", "#898781"
SURFACE, PLANE, GRID, DIMMED = "#1a1a19", "#0d0d0d", "#2c2c2a", "#75746e"
# DIMMED: 3.7:1 on SURFACE (WCAG 1.4.11 asks 3:1 for a mark you can click), drawn at full opacity.

CSS = f"""
<style>
.de-eyebrow {{ font: 600 0.75rem/1 'Fira Code', monospace; letter-spacing: .14em; color: {MUTED};
              text-transform: uppercase; margin: 0 0 .5rem 0; }}
.de-title {{ font-size: 2rem; font-weight: 700; line-height: 1.2; margin: 0 0 .25rem 0; padding: 0; color: {INK}; }}
.de-h {{ font-size: 1rem; font-weight: 600; margin: .4rem 0 .3rem 0; padding: 0; color: {INK}; }}
.de-sr {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }}
.stTabs [role=tab] p {{ font-size: 1rem; font-weight: 500; }}
.de-sub {{ color: {INK_2}; margin: .35rem 0 0 0; font-size: .95rem; }}
.de-answer {{ font-size: 1.15rem; line-height: 1.5; color: {INK}; margin: .2rem 0 1rem 0; }}
.de-answer b {{ font-weight: 600; }}
.de-chip {{ display: inline-block; padding: .1rem .55rem; margin: 0 .35rem .35rem 0; border-radius: 999px;
           border: 1px solid {GRID}; background: {SURFACE}; color: {INK_2}; font-size: .8rem; }}
.de-dot {{ display: inline-block; width: .6rem; height: .6rem; border-radius: 50%; margin-right: .35rem;
          vertical-align: baseline; }}
.de-card {{ border: 1px solid {GRID}; border-radius: 6px; background: {SURFACE}; padding: .7rem .85rem;
           margin-bottom: .55rem; }}
.de-card .meta {{ color: {MUTED}; font-size: .8rem; }}
.de-card .text {{ color: {INK_2}; font-size: .9rem; line-height: 1.5; margin-top: .25rem; }}
.de-card mark {{ background: rgba(201,133,0,.32); color: {INK}; padding: 0 .1rem; border-radius: 2px; }}
.de-num {{ font-family: 'Fira Code', monospace; }}
.de-note {{ color: {MUTED}; font-size: .8rem; line-height: 1.45; }}
</style>
"""


def connect(attempts=5):
    """A few retries: the database may still be restarting."""
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(**DB, connect_timeout=5)
        except psycopg.OperationalError:
            if attempt == attempts:
                raise
            time.sleep(2 * attempt)


def query(conn, sql, params=None):
    """Run one query and return the rows as a DataFrame."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])


def timed_query(conn, sql, params):
    """The same, plus its time in ms (time.perf_counter). Never cached: the time is real."""
    t0 = time.perf_counter()
    df = query(conn, sql, params)
    return df, (time.perf_counter() - t0) * 1000


def read_named_queries(path):
    """Split sql/queries.sql on '-- name: <name>' lines (same as the loader)."""
    queries, name, lines = {}, None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(lines).strip().rstrip(";")
            name, lines = line.split(":", 1)[1].strip(), []
        elif name:
            lines.append(line)
    if name:
        queries[name] = "\n".join(lines).strip().rstrip(";")
    return queries


Q = read_named_queries(QUERIES_FILE)


@st.cache_data(ttl=60)   # what the loader wrote changes only when the loader runs again
def load_info():
    with connect() as conn:
        return {
            "info": dict(query(conn, "SELECT key, value FROM load_info").values),
            # The step timings of the last loader run, in the order the steps ran.
            "timings": query(conn, """
                SELECT step, to_char(seconds, 'FM9990.00') AS seconds,
                       coalesce(to_char(rows, 'FM999,999,999'), '') AS rows
                FROM pipeline_timings
                WHERE run_id = (SELECT value FROM load_info WHERE key = 'run_id')
                ORDER BY finished_at, seconds"""),
        }


@st.cache_data(ttl=60)
def load_atlas():
    with connect() as conn:
        points = query(conn, Q["atlas_points"])
        regions = query(conn, Q["atlas_regions"])
    regions["short"] = [", ".join(n.split(", ")[:2]) for n in regions.name]   # on the map: two words
    points["kind"] = [("Rx and OTC" if rx and otc else "Rx only" if rx else "OTC only" if otc else "other")
                      for rx, otc in zip(points.n_rx, points.n_otc)]
    points["name"] = points.substance_key.map(pretty)
    points["class"] = points.pharm_class_epc.str.replace(" [EPC]", "", regex=False).fillna(NO_CLASS)
    return points, regions


def pretty(key):
    """'ACETAMINOPHEN + CAFFEINE' -> 'Acetaminophen + caffeine' (sentence case, easier to read)."""
    low = key.lower()
    return low[:1].upper() + low[1:]


def plural(n, one, many):
    return f"{n:,} {one if n == 1 else many}"


def use_example():
    """Pills callback: copy the picked example into the search box, then clear the pill."""
    if st.session_state.example:
        st.session_state.condition = st.session_state.example
        st.session_state.example = None


def label_card(container, brand, manufacturer, date, product_type, snippet, highlighted):
    """One label: brand, maker, date, type, and the text around the match (escaped, then <mark>)."""
    text = html.escape(snippet or "")
    if highlighted:   # ts_headline marks the match with <b>...</b>
        text = text.replace("&lt;b&gt;", "<mark>").replace("&lt;/b&gt;", "</mark>")
    date = date.isoformat() if date else "no date"
    container.html(
        f"<div class='de-card'><b>{html.escape(brand or '(no brand name)')}</b>"
        f"<div class='meta'>{html.escape(manufacturer or '')}, {date}, {product_type}</div>"
        f"<div class='text'>… {text} …</div></div>")


def new_map():
    """The focus moved without a click on the map (box, table row, new search): draw a new chart,
    so the map forgets its old click and a click on that same dot works again (interaction test, bug 1).
    The zoom is reset too: the price of a new chart."""
    st.session_state.map_gen = st.session_state.get("map_gen", 0) + 1
    st.session_state.last_click = None


def kind_chip(kind):
    return (f"<span class='de-chip'><span class='de-dot' style='background:{KIND_COLORS[kind]}'></span>"
            f"{kind}</span>")


st.set_page_config(page_title="Drug explorer: which drugs treat this condition?", layout="wide",
                   page_icon=":material/medication:")
st.html(CSS)
loaded = load_info()
info, timings = loaded["info"], loaded["timings"]
points, regions = load_atlas()

# ---------------------------------------------------------------- header and the question
st.html(
    "<p class='de-eyebrow'>Drug explorer, openFDA labels</p>"
    "<h1 class='de-title'>Which drugs treat this condition?</h1>"
    f"<p class='de-sub'>A word search in the “Indications and usage” section of "
    f"{int(info['rows_loaded']):,} FDA drug labels "
    f"(export of {info['export_date']}). Not medical advice.</p>")

st.session_state.setdefault("condition", "migraine")
st.session_state.setdefault("map_gen", 0)
c_search, c_type = st.columns([3, 2], vertical_alignment="bottom")
condition = c_search.text_input("Condition, in English", key="condition", max_chars=80,
                                placeholder="for example: migraine, type 2 diabetes").strip()
choice = c_type.segmented_control("Labels", list(PRODUCT_TYPES), default="All", key="ptype",
                                  help="Rx: prescription labels. OTC: over the counter labels.") or "All"
st.pills("Examples", EXAMPLES, key="example", on_change=use_example, label_visibility="collapsed")
params = {"condition": condition, "product_type": PRODUCT_TYPES[choice]}
only = "" if choice == "All" else f" Only {TYPE_WORDS[choice]} labels are counted."

with connect() as conn:            # not cached: the times shown are real queries every time
    summary, ms_summary = timed_query(conn, Q["condition_summary"], params)
    drugs, ms_drugs = timed_query(conn, Q["drugs_for_condition"], params)
    hits, ms_hits = timed_query(conn, Q["condition_hits"], params)
s = summary.iloc[0]
found = bool(condition) and s.n_labels > 0

# ---------------------------------------------------------------- the answer, in one sentence
if found:
    n_other = s.n_labels - s.n_rx - s.n_otc            # e.g. 'Cellular Therapy': neither Rx nor OTC
    other = f", {n_other:,} other" if n_other else ""
    top = ", ".join(f"{pretty(k).lower()} ({n})" for k, n in drugs.head(3)[["substance_key", "n_labels"]].values)
    st.html(f"<p class='de-answer'><b>{plural(s.n_ingredients, 'active ingredient', 'active ingredients')}</b> "
            f"{'is' if s.n_ingredients == 1 else 'are'} named for “{html.escape(condition)}” in <b>{plural(s.n_labels, 'FDA label', 'FDA labels')}</b> "
            f"({s.n_rx:,} prescription, {s.n_otc:,} over the counter{other}). "
            f"Most labels: {html.escape(top)}.{only}</p>")
elif not condition:
    st.info("Type a condition above, or pick an example. The map below shows every ingredient.")
else:
    st.warning(f"No label's indications match “{condition}”. Try another word or a shorter phrase "
               "(the search looks for the exact words, in this order, and ignores common words like “the”).")

tab_atlas, tab_top, tab_about = st.tabs(["Atlas", "Top ingredients", "About the data"])

# ---------------------------------------------------------------- tab 1: the atlas
with tab_atlas:
    if points.empty:      # e.g. a small sample: too few ingredients with enough labels (loader log)
        st.info("The atlas was not built for this load: too few ingredients have "
                f"{info.get('atlas_min_labels', '5')} labels or more. The other tabs work as usual.")
    else:
        pts = points.merge(hits, on="substance_key", how="left")
        pts["n_hits"] = pts.n_hits.fillna(0).astype(int)
        pts["match"] = pts.n_hits > 0
        on_map = int(pts.match.sum())
        # Which ingredient the panel shows: a click on a dot, a row of the neighbours table or the
        # box above the panel. Default for a new search: the matching ingredient with the most labels.
        default = (pts[pts.match].sort_values("n_hits", ascending=False).substance_key.iloc[0] if on_map
                   else pts.sort_values("n_labels", ascending=False).substance_key.iloc[0])
        if st.session_state.get("focus_for") != (condition, choice):
            st.session_state.focus = default
            st.session_state.focus_for = (condition, choice)
            new_map()

        c_map, c_panel = st.columns([13, 7], gap="large")
        with c_map:
            pick = alt.selection_point(name="pick", fields=["substance_key"], on="click", empty=False)
            zoom = alt.selection_interval(name="zoom", bind="scales")
            no_axis = alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None)
            x = alt.X("x:Q", axis=no_axis, scale=alt.Scale(zero=False, nice=False, padding=12))
            y = alt.Y("y:Q", axis=no_axis, scale=alt.Scale(zero=False, nice=False, padding=12))
            tooltip = [alt.Tooltip("name:N", title="Ingredient"), alt.Tooltip("kind:N", title="Its labels"),
                       alt.Tooltip("n_labels:Q", title="Labels", format=","),
                       alt.Tooltip("region_name:N", title="Region")]
            if found:
                tooltip.insert(3, alt.Tooltip("n_hits:Q", title=f"Mention “{condition}”", format=","))
            pts["is_focus"] = pts.substance_key == st.session_state.focus     # for the ring, below
            base = alt.Chart(pts).encode(x=x, y=y)
            # Every dot: grey when a search is on and it does not match, else the colour of its kind.
            kinds = [k for k in KIND_COLORS if k in set(pts.kind)]    # no legend entry for a kind not on the map
            lit = "datum.match || !" + ("true" if found else "false")      # coloured, not greyed out
            size_by = "n_hits" if found else "n_labels"
            size = alt.Size(f"{size_by}:Q", scale=alt.Scale(type="sqrt", range=[60, 560] if found else [18, 440],
                                                             domain=[1, max(int(pts[size_by].max()), 2)]),
                            title=("Mentions" if found else "Labels"),
                            legend=alt.Legend(orient="top", titleColor=INK_2, labelColor=INK_2,
                                              symbolFillColor=MUTED, symbolStrokeWidth=0, tickCount=3))
            dots = base.mark_circle(stroke=PLANE, strokeWidth=0.6).encode(
                color=alt.condition(
                    lit,
                    alt.Color("kind:N", title="Its labels are",
                              scale=alt.Scale(domain=kinds, range=[KIND_COLORS[k] for k in kinds]),
                              legend=alt.Legend(orient="top", direction="horizontal", titleColor=INK_2,
                                                labelColor=INK_2, symbolStrokeWidth=0)),
                    alt.value(DIMMED)),
                # a dot that does not match keeps a small fixed size: it shows the shape of the map
                size=alt.condition("datum.match", size, alt.value(26)) if found else size,
                opacity=alt.condition(lit, alt.value(0.92), alt.value(1.0)),
                order=alt.Order("match:O"),           # the matching dots are drawn on top of the grey ones
                tooltip=tooltip,
            ).add_params(pick, zoom)
            # The open ingredient: a light ring on a dark halo, big enough to find on a dense area.
            # The focus is a data column, not a literal in the spec. (Known limit: the page still redraws
            # the chart after a click, so a zoom returns to the full view; docs/decision_log.md, D-57.)
            focused = base.transform_filter("datum.is_focus")
            focus_ring = (focused.mark_circle(size=900, filled=False, stroke=PLANE, strokeWidth=5)
                          + focused.mark_circle(size=900, filled=False, stroke=INK, strokeWidth=2))
            # Region names: left-aligned near the left edge, right-aligned near the right one, so none
            # is cut by the frame; a dark halo keeps them readable over the dots.
            layers = [dots]
            for align, keep in (("left", alt.datum.x < -1.2), ("center", (alt.datum.x >= -1.2) & (alt.datum.x <= 1.2)),
                                ("right", alt.datum.x > 1.2)):
                names = alt.Chart(regions).transform_filter(keep).encode(x=x, y=y, text="short:N")
                layers += [names.mark_text(align=align, fontSize=11, fontWeight=600, stroke=PLANE, strokeWidth=5,
                                           strokeOpacity=0.9),
                           names.mark_text(align=align, fontSize=11, fontWeight=600, color=INK_2)]
            # Read by screen readers as the chart's name (Vega-Lite description -> aria-label).
            description = (f"Scatter map of {len(pts):,} active ingredients placed by the words of their labels"
                           + (f"; {on_map:,} mention {condition}" if found else "")
                           + ". The open ingredient has a light ring and is named in the panel beside the map. "
                           "Keyboard: use the box 'Ingredient on the map'.")
            chart = alt.layer(*layers, focus_ring).properties(   # the ring last: never under a name
                height=720, description=description).configure_view(
                stroke=None, fill=SURFACE).configure(background=SURFACE)
            event = st.altair_chart(chart, on_select="rerun", selection_mode="pick", key=f"atlas_{st.session_state.map_gen}",
                                    width="stretch")
            clicked = [p["substance_key"] for p in event.selection.get("pick", [])] if event else []
            # A click is new when it differs from the last one handled. The selection stays in the
            # chart after the focus moves another way, so those ways draw a new chart (new_map).
            if clicked and clicked[0] != st.session_state.get("last_click"):
                st.session_state.last_click = clicked[0]
                st.session_state.focus = clicked[0]
                st.rerun()        # draw the ring and the panel for the dot just clicked
            st.html(
                f"<p class='de-note'>{plural(len(pts), 'ingredient', 'ingredients')} with at least "
                f"{info.get('atlas_min_labels', '5')} labels, placed by the words of their indications: "
                "close dots are described with similar words. "
                + (f"<b>{on_map:,}</b> of them mention “{html.escape(condition)}”, the coloured dots "
                   f"(the other {s.n_ingredients - on_map:,} matching ingredients have fewer labels and are not on the map). "
                   if found else "")
                + "Click a dot to open it; scroll to zoom, drag to move, double-click to reset (a click also resets the zoom). Keyboard: the box "
                  "“Ingredient on the map”, or a row of the table (Shift+Space). "
                "The axes have no unit: only closeness means something, and near does not mean interchangeable.</p>")

        with c_panel:
            if "go_to" in st.session_state:        # a row picked in the neighbours table, last run
                st.session_state.focus = st.session_state.pop("go_to")
                new_map()
            keys = points.substance_key.tolist()
            focus = st.selectbox("Ingredient on the map", keys, key="focus", format_func=pretty, on_change=new_map,
                                 help="Type to search. The same as clicking its dot: the keyboard way to use the map.")
            row = pts.set_index("substance_key").loc[focus]
            klass = "" if row["class"] == NO_CLASS else f"<span class='de-chip'>Class: {html.escape(row['class'])}</span>"
            st.html(f"<div>{kind_chip(row.kind)}<span class='de-chip'>Region: {html.escape(row.region_name)}</span>"
                    f"{klass}</div>"
                    # read aloud by screen readers when the panel changes (WCAG 4.1.3)
                    f"<div class='de-sr' role='status' aria-live='polite'>Showing {html.escape(pretty(focus))}: "
                    f"{row.n_labels:,} labels" + (f", {row.n_hits:,} mention {html.escape(condition)}" if found else "") + "</div>")
            m1, m2 = st.columns(2)
            m1.metric("Labels, all types", f"{row.n_labels:,}", border=True)
            m2.metric(f"Mention “{condition[:18]}”" if found else "Mention the search",
                      f"{row.n_hits:,}" if found else "–", border=True)
            with connect() as conn:
                near, ms_near = timed_query(conn, Q["atlas_neighbours"], {"substance_key": focus})
                if row.n_hits:
                    said, ms_said = timed_query(conn, Q["labels_for_drug"], params | {"substance_key": focus})
                else:
                    said, ms_said = timed_query(conn, Q["labels_of_drug"], params | {"substance_key": focus})
            st.html("<h3 class='de-h'>Most similar ingredients</h3>")
            near["Ingredient"] = near.neighbour_key.map(pretty)
            near["Mentions it"] = near.neighbour_key.isin(hits.substance_key) if found else False
            picked = st.dataframe(
                near[["Ingredient", "similarity", "Mentions it"]], hide_index=True, height=280, width="stretch",
                on_select="rerun", selection_mode="single-row", key=f"near_{focus}",
                column_config={
                    "Ingredient": st.column_config.TextColumn(width="medium"),
                    "similarity": st.column_config.ProgressColumn("Similarity", min_value=0, max_value=1, format="%.2f",
                                                                  width="small"),
                    "Mentions it": st.column_config.CheckboxColumn("Match", width="small",
                                                                   help="One of its labels mentions the search"),
                })
            if picked.selection.rows:
                st.session_state.go_to = near.neighbour_key.iloc[picked.selection.rows[0]]
                st.rerun()        # the box above already exists in this run: change it in the next one
            st.caption("Similarity: cosine of the two word profiles, 0 to 1. Pick a row to open it "
                       "(keyboard: Shift+Space on the row).")
            if row.n_hits:
                st.html(f"<h3 class='de-h'>What its labels say about “{html.escape(condition)}”</h3>")
            else:
                st.html("<h3 class='de-h'>What its newest labels say"
                        + (f" (none mentions “{html.escape(condition)}”)" if found else "") + "</h3>")
            box = st.container(height=300)
            for r in said.head(5).itertuples():
                label_card(box, r.brand_name, r.manufacturer, r.effective_date, r.product_type, r.snippet,
                           highlighted=bool(row.n_hits))
            st.caption(f"query time: {ms_near:.0f} ms (atlas_neighbours) + {ms_said:.0f} ms "
                       f"({'labels_for_drug' if row.n_hits else 'labels_of_drug'})")

# ---------------------------------------------------------------- tab 2: the ranking
with tab_top:
    if not found:
        st.info("Type a condition above to see its ranking.")
    else:
        drugs["other"] = drugs.n_labels - drugs.n_rx - drugs.n_otc
        drugs["name"] = drugs.substance_key.map(pretty)
        c_chart, c_table = st.columns([1, 1], gap="large")
        with c_chart:
            st.html("<h3 class='de-h'>The 15 ingredients with the most labels</h3>")
            types = [t for t, n in (("Rx", drugs.n_rx), ("OTC", drugs.n_otc), ("other", drugs.other))
                     if n.head(15).sum()]       # no legend entry for a type with no label
            bars = drugs.head(15).rename(columns={"n_rx": "Rx", "n_otc": "OTC"}).melt(
                id_vars=["name", "n_labels"], value_vars=["Rx", "OTC", "other"],
                var_name="type", value_name="labels")
            st.altair_chart(alt.Chart(bars).mark_bar(stroke=SURFACE, strokeWidth=2).encode(
                x=alt.X("labels:Q", title="Labels that mention the condition",
                        axis=alt.Axis(gridColor=GRID, domainColor=GRID, labelColor=MUTED, titleColor=INK_2)),
                y=alt.Y("name:N", title=None, sort=alt.SortField("n_labels", order="descending"),
                        axis=alt.Axis(labelLimit=260, labelColor=INK_2, labelFontSize=12, domain=False, ticks=False)),
                color=alt.Color("type:N", title="Label", scale=alt.Scale(
                    domain=types, range=[BAR_COLORS[t] for t in types]),
                    legend=alt.Legend(orient="top", titleColor=INK_2, labelColor=INK_2, titlePadding=6, padding=8)),
                order=alt.Order("type:N", sort="descending"),
                tooltip=[alt.Tooltip("name", title="Ingredient"), alt.Tooltip("type", title="Label"),
                         alt.Tooltip("labels", title="Labels"), alt.Tooltip("n_labels", title="All types")],
            ).properties(height=alt.Step(24)).configure_view(stroke=None).configure(background=SURFACE),
                width="stretch")
            st.caption(f"query time: {ms_drugs:.0f} ms (drugs_for_condition) + {ms_summary:.0f} ms "
                       f"(condition_summary) + {ms_hits:.0f} ms (condition_hits), full-text search "
                       "through the GIN index on labels.tsv")
        with c_table:
            st.html(f"<h3 class='de-h'>Top {len(drugs)} of {s.n_ingredients:,}</h3>")
            drugs["class"] = drugs.pharm_class_epc.str.replace(" [EPC]", "", regex=False).fillna("–")
            st.dataframe(drugs[["name", "n_labels", "n_rx", "n_otc", "n_labels_all_conditions", "class"]].rename(columns={
                "name": "Active ingredient", "n_labels": "Labels", "n_rx": "Rx", "n_otc": "OTC",
                "n_labels_all_conditions": "All", "class": "Class"}), hide_index=True,
                height=420, column_config={
                    "Active ingredient": st.column_config.TextColumn(width="medium"),
                    "All": st.column_config.NumberColumn(width="small", help="All its labels, whatever they treat"),
                    "Class": st.column_config.TextColumn(help="Established pharmacologic class; – when none")}
                | {c: st.column_config.NumberColumn(width="small") for c in ["Labels", "Rx", "OTC"]})
            st.caption("Labels: those whose indications mention the condition; All: all its labels, whatever "
                       "they treat. Class: the most common established pharmacologic class in the ingredient's "
                       "labels; – when none has one (most labels have none).")

        st.html("<h3 class='de-h'>What the labels say</h3>")
        pick_i = st.selectbox("Active ingredient", drugs.index, label_visibility="collapsed",
                              format_func=lambda i: f"{drugs.name[i]} ({drugs.n_labels[i]:,} labels)")
        with connect() as conn:
            labels, ms_labels = timed_query(conn, Q["labels_for_drug"],
                                            params | {"substance_key": drugs.substance_key[pick_i]})
        st.caption(f"{len(labels)} of {drugs.n_labels[pick_i]:,} labels, newest first.{only} "
                   f"query time: {ms_labels:.0f} ms (labels_for_drug, with ts_headline on the rows shown)")
        box = st.container(height=420)    # up to 20 labels: scroll inside the box, not the whole page
        for r in labels.itertuples():
            label_card(box, r.brand_name, r.manufacturer, r.effective_date, r.product_type, r.snippet, True)

# ---------------------------------------------------------------- tab 3: what this is, and the data
with tab_about:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("#### What this search is")
        st.markdown(
            "A text search in the “Indications and usage” section of FDA labels, not a medical database. "
            "A label is counted when its indications contain the words you typed (stemmed: “migraines” "
            "finds “migraine”), whatever the sentence says around them. Synonyms are not matched "
            "(“heart attack” and “myocardial infarction” give different answers: try both), and a mention "
            "is not always a treatment: about 40% of the “cancer” labels are sunscreens, because their labels "
            "say “decreases the risk of skin cancer”. **Not medical advice.**")
        st.button("Try “cancer”", on_click=lambda: st.session_state.update(condition="cancer"))
        st.markdown("#### How the atlas is made")
        st.markdown(
            "The idea comes from XO by XLN Audio, a map of drum sounds where similar sounds sit together. "
            "Here each dot is an active ingredient with at least "
            f"{info.get('atlas_min_labels', '5')} labels. For each one the loader counts which words its "
            "labels use, weights the distinctive ones (TF-IDF), merges words that travel together (SVD, 40 "
            "dimensions) and draws the result in two dimensions (t-SNE). Regions are groups of nearby dots "
            "(k-means), named by their three most distinctive words, chosen by the computer. "
            "Close dots are described with similar words: that is all the map knows. "
            "It is not pharmacology, and two close ingredients are not interchangeable.")
    with c2:
        st.markdown("#### Where the data comes from")
        st.markdown(
            f"openFDA drug labels ({info['licence']}), export of {info['export_date']}, downloaded on "
            f"{info['downloaded_on']} from {info['source_url']}. Labels loaded: "
            f"{int(info['rows_loaded']):,} of {int(info['labels_in_export']):,} in the export (only labels "
            f"with an active-ingredient name and an indications text). Sample fraction: {info['sample_fraction']}.")
        st.markdown("#### Last loader run, seconds per step")
        st.caption(info["run_id"])
        st.dataframe(timings.rename(columns={"step": "Step", "seconds": "Seconds", "rows": "Rows"}),
                     hide_index=True, width="stretch")

st.caption("Built from public FDA data. Not medical advice.")
