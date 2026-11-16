"""Streamlit dashboard for exploring active ingredients by medical condition.

Users enter a condition name and the app lists the active ingredients whose FDA
'Indications and usage' text mentions it via PostgreSQL full-text search
(using the GIN index on labels.tsv). All SQL queries live in sql/queries.sql
and are executed against the 'db' service inside Docker Compose.
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
    host=os.environ.get("DB_HOST", "db"),          # Docker Compose service hostname (never use localhost)
    port=int(os.environ.get("DB_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
QUERIES_FILE = Path(__file__).parent / "sql" / "queries.sql"
PRODUCT_TYPES = {"All": "all", "Prescription (Rx)": "Rx", "Over the counter (OTC)": "OTC"}
EXAMPLES = ["migraine", "epilepsy", "asthma", "hypertension", "acne"]
NO_CLASS = "not in label data"


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


@st.cache_data(ttl=60)   # Cache loader metadata briefly since it only updates when the loader runs again
def load_info():
    with connect() as conn:
        return {
            "info": dict(query(conn, "SELECT key, value FROM load_info").values),
            # Step durations and row counts from the latest loader execution
            "timings": query(conn, """
                SELECT step, to_char(seconds, 'FM9990.00') AS seconds,
                       coalesce(to_char(rows, 'FM999,999,999'), '') AS rows
                FROM pipeline_timings
                WHERE run_id = (SELECT value FROM load_info WHERE key = 'run_id')
                ORDER BY finished_at, seconds"""),
        }


def plural(n, one, many):
    return f"{n:,} {one if n == 1 else many}"


def footer(info, timings):
    st.divider()
    st.caption(
        f"**Data:** openFDA drug labels ({info['licence']}), export of {info['export_date']}, "
        f"downloaded on {info['downloaded_on']} from {info['source_url']}. "
        f"Labels loaded: {int(info['rows_loaded']):,} of {int(info['labels_in_export']):,} in the export "
        f"(only labels with an active-ingredient name and an indications text). "
        f"Sample fraction: {info['sample_fraction']}."
    )
    st.caption(f"Last loader run ({info['run_id']}), seconds per step:")
    st.table(timings.rename(columns={"step": "Step", "seconds": "Seconds", "rows": "Rows"}).set_index("Step"))
    st.caption("Not medical advice: the page counts mentions in FDA labels, it does not say that a drug works.")


def use_example(word):
    st.session_state.condition = word   # a callback runs before the page is drawn again


st.set_page_config(page_title="Which drugs treat this condition?", layout="centered")
Q = read_named_queries(QUERIES_FILE)
loaded = load_info()
info, timings = loaded["info"], loaded["timings"]

# --- Condition search input and Rx/OTC filter ---
st.title("Which drugs treat this condition?")
st.session_state.setdefault("condition", "migraine")
condition = st.text_input("Condition", key="condition", max_chars=80).strip()
cols = st.columns([0.5] + [1] * len(EXAMPLES), vertical_alignment="center")
cols[0].caption("Try:")
for col, word in zip(cols[1:], EXAMPLES):
    col.button(word, on_click=use_example, args=(word,), width="stretch")
choice = st.radio("Labels", list(PRODUCT_TYPES), horizontal=True)
params = {"condition": condition, "product_type": PRODUCT_TYPES[choice]}

with connect() as conn:            # not cached: the times shown are real queries every time
    summary, ms_summary = timed_query(conn, Q["condition_summary"], params)
    drugs, ms_drugs = timed_query(conn, Q["drugs_for_condition"], params)
s = summary.iloc[0]

# --- Summary headline with ingredient and label counts ---
if not condition or s.n_labels == 0:
    st.warning(f"No label's indications match “{condition}”. Try another word or a shorter phrase "
               "(the search looks for the exact words, in this order, and ignores common words like “the”).")
    footer(info, timings)
    st.stop()
n_other = s.n_labels - s.n_rx - s.n_otc            # e.g. 'Cellular Therapy': neither Rx nor OTC
other = f", {n_other:,} other" if n_other else ""
filtered = "" if choice == "All" else f" Only {choice.split(' (')[0].lower()} labels are counted."
st.markdown(
    f"### {plural(s.n_ingredients, 'active ingredient is', 'active ingredients are')} named for "
    f"“{condition}” in {plural(s.n_labels, 'FDA label', 'FDA labels')} "
    f"({s.n_rx:,} prescription, {s.n_otc:,} over the counter{other})."
)
top = ", ".join(f"{k.lower()} ({n})" for k, n in drugs.head(5)[["substance_key", "n_labels"]].values)
st.markdown(f"**Most labels:** {top}.{filtered}")
st.caption(f"query time: {ms_drugs:.0f} ms (drugs_for_condition) + {ms_summary:.0f} ms (condition_summary), "
           "full-text search through the GIN index on labels.tsv")

# --- Horizontal bar chart: top 15 ingredients split by Rx vs OTC ---
st.subheader("The ingredients with the most labels")
drugs["other"] = drugs.n_labels - drugs.n_rx - drugs.n_otc
bars = drugs.head(15).rename(columns={"n_rx": "Rx", "n_otc": "OTC"}).melt(
    id_vars=["substance_key", "n_labels"], value_vars=["Rx", "OTC", "other"],
    var_name="type", value_name="labels")
st.altair_chart(alt.Chart(bars).mark_bar().encode(
    x=alt.X("labels:Q", title="Labels that mention the condition"),
    y=alt.Y("substance_key:N", title=None, sort=alt.SortField("n_labels", order="descending"),
            axis=alt.Axis(labelLimit=260)),
    color=alt.Color("type:N", title="Label", scale=alt.Scale(
        domain=["Rx", "OTC", "other"], range=["#4c78a8", "#f58518", "#bab0ac"])),
    order=alt.Order("type:N", sort="descending"),
    tooltip=[alt.Tooltip("substance_key", title="Ingredient"), alt.Tooltip("type", title="Label"),
             alt.Tooltip("labels", title="Labels"), alt.Tooltip("n_labels", title="All types")],
).properties(height=alt.Step(22)), width="stretch")

# ---------------------------------------------------------------- table: the top 25
drugs["class"] = drugs.pharm_class_epc.str.replace(" [EPC]", "", regex=False).fillna(NO_CLASS)
table = drugs[["substance_key", "n_labels", "n_rx", "n_otc", "n_labels_all_conditions", "class"]]
st.dataframe(table.rename(columns={
    "substance_key": "Active ingredient", "n_labels": "Labels", "n_rx": "Rx", "n_otc": "OTC",
    "n_labels_all_conditions": "All its labels", "class": "Pharmacological class"}), hide_index=True,
    column_config={"Active ingredient": st.column_config.TextColumn(width=240)}
    | {c: st.column_config.NumberColumn(width="small") for c in ["Labels", "Rx", "OTC", "All its labels"]})
st.caption(f"Top {len(drugs)} of {s.n_ingredients:,}. Labels: those whose indications mention the condition; "
           "all its labels: whatever they treat. Class: the most common established pharmacologic "
           "class in the ingredient's labels (most labels have none).")

# ---------------------------------------------------------------- drill-down: one ingredient's labels
st.subheader("What the labels say")
pick = st.selectbox("Active ingredient", drugs.index,
                    format_func=lambda i: f"{drugs.substance_key[i]} ({drugs.n_labels[i]:,} labels)")
key = drugs.substance_key[pick]
with connect() as conn:
    labels, ms_labels = timed_query(conn, Q["labels_for_drug"], params | {"substance_key": key})
st.caption(f"{len(labels)} of {drugs.n_labels[pick]:,} labels, newest first.{filtered} "
           f"query time: {ms_labels:.0f} ms (labels_for_drug, with ts_headline on the rows shown)")
box = st.container(height=480)    # Scrollable container holding up to 20 matching label snippets
for r in labels.itertuples():
    # PostgreSQL ts_headline wraps matched terms in <b>...</b> tags; escape everything else before converting to <mark>
    snippet = html.escape(r.snippet).replace("&lt;b&gt;", "<mark>").replace("&lt;/b&gt;", "</mark>")
    date = r.effective_date.isoformat() if r.effective_date else "no date"
    box.html(f"<div><b>{html.escape(r.brand_name or '(no brand name)')}</b> "
             f"<span style='color:grey'>, {html.escape(r.manufacturer or '')}, {date}, {r.product_type}</span>"
             f"<br>… {snippet} …</div>")

# --- Methodology notes and search limitations ---
st.subheader("What this search is")
st.info(
    "A text search in the “Indications and usage” section of FDA labels, not a medical database. "
    "A label is counted when its indications contain the words you typed (stemmed: “migraines” "
    "finds “migraine”), whatever the sentence says around them. Synonyms are not matched "
    "(“heart attack” and “myocardial infarction” give different answers: try both), and a mention "
    "is not always a treatment: "
    "about 40% of the “cancer” labels are sunscreens, because their labels say “decreases the risk of skin cancer”. "
    "**Not medical advice.**"
)
st.button("Try “cancer”", on_click=use_example, args=("cancer",))

footer(info, timings)
