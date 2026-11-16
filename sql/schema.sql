-- Schema for the drug explorer (PostgreSQL 16).
-- Built in four steps:
--   1 find the things      -> labels (one FDA label each), drugs (one active ingredient, or combination)
--   2 name each row        -> labels.set_id (the FDA's id of a label and all its versions),
--                             drugs.substance_key (the sorted ingredient names)
--   3 connect them         -> labels.substance_key -> drugs.substance_key
--   4 store each fact once -> the counts and the most common class of an ingredient live only in drugs
-- Every statement is idempotent: the loader runs this file on every start.

-- One row per label that can answer the question: it has an "Indications and usage" text
-- and an active-ingredient name (78,472 of 262,907 labels in the export of 5 Nov 2026).
CREATE TABLE IF NOT EXISTS labels (
    set_id          UUID PRIMARY KEY,     -- the label's set id: the same across versions of one label
    label_id        TEXT    NOT NULL,     -- id of this version of the label
    version         INTEGER,
    effective_date  DATE,                 -- effective_time of this version
    product_type    TEXT    NOT NULL,     -- 'Rx' | 'OTC' | other (e.g. 'Cellular Therapy')
    substance_key   TEXT    NOT NULL,     -- e.g. 'ACETAMINOPHEN + ASPIRIN + CAFFEINE'
    generic_name    TEXT,
    brand_name      TEXT,
    manufacturer    TEXT,
    route           TEXT,                 -- e.g. 'ORAL'; several joined with '; '
    pharm_class_epc TEXT,                 -- established pharmacologic class; NULL for most labels
    bucket          SMALLINT NOT NULL,    -- md5(set_id) mod 4: 25% = {0}, 50% = {0,1}, 100% = {0,1,2,3}
    indications     TEXT    NOT NULL,     -- the "Indications and usage" section, whitespace normalised
    -- The words of the indications, stemmed and without stop words ('migraines' -> 'migrain'),
    -- computed once when the row is written and stored on disk, so a query does not recompute it
    -- for every row. Measured here at 100%, 'migraine', benchmark v3 means: 3.21 s on the fly against
    -- 3.22 ms with the GIN index (measure/results_v3/summary.csv; v1: 3.57 s and 2.76 ms).
    tsv             TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', indications)) STORED
);

-- One row per active ingredient (or combination), computed from labels by the loader
-- (sql/queries.sql, "drugs").
CREATE TABLE IF NOT EXISTS drugs (
    substance_key   TEXT PRIMARY KEY,
    n_labels        INTEGER NOT NULL,
    n_rx            INTEGER NOT NULL,
    n_otc           INTEGER NOT NULL,
    pharm_class_epc TEXT                  -- the most common class among its labels; NULL when none has one
);

-- What each loader run did: one row per step (filled by the loader, never emptied).
CREATE TABLE IF NOT EXISTS pipeline_timings (
    run_id      TEXT             NOT NULL,
    step        TEXT             NOT NULL,
    seconds     DOUBLE PRECISION NOT NULL,
    rows        BIGINT,
    detail      TEXT,
    started_at  TIMESTAMPTZ      NOT NULL,   -- wall clock at the start and the end of the step,
    finished_at TIMESTAMPTZ      NOT NULL    -- taken in the loader (seconds come from time.perf_counter)
);

-- Where the data came from (shown on the dashboard).
CREATE TABLE IF NOT EXISTS load_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
