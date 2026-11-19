-- Labels also say what a drug is NOT for: "Baclofen is not indicated in the treatment of
-- skeletal muscle spasm". We do not want that label under "muscle spasms", so the words
-- from "not indicated" (or recommended, approved, intended, used, for use) to the end of
-- the sentence are replaced by [...] before the text is indexed.
CREATE OR REPLACE FUNCTION searchable(indications TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT regexp_replace(
        indications,
        '\m(not|never)(\s+\w+)?\s+(indicated|recommended|approved|intended|used|for\s+use)\M[^.]*',
        '[...]', 'gi')
$$;

-- One row per FDA label that has an ingredient name and an indications text.
CREATE TABLE labels (
    set_id          UUID PRIMARY KEY,   -- the FDA's id of the label
    label_id        TEXT NOT NULL,      -- id of this version
    version         INTEGER,
    effective_date  DATE,
    product_type    TEXT NOT NULL,      -- 'Rx', 'OTC', or the FDA's word for the few others
    substance_key   TEXT NOT NULL,      -- 'ACETAMINOPHEN + ASPIRIN + CAFFEINE'
    generic_name    TEXT,
    brand_name      TEXT,
    manufacturer    TEXT,
    route           TEXT,
    pharm_class_epc TEXT,               -- drug class, missing on most labels
    bucket          SMALLINT NOT NULL,  -- 0 to 3, used for the 25% and 50% samples
    indications     TEXT NOT NULL,
    -- the words we search, stemmed: 'migraines' is stored as 'migrain'
    tsv             TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', searchable(indications))) STORED
);

-- One row per active ingredient or combination, counted from labels (drugs.sql).
CREATE TABLE drugs (
    substance_key   TEXT PRIMARY KEY,
    n_labels        INTEGER NOT NULL,
    n_rx            INTEGER NOT NULL,
    n_otc           INTEGER NOT NULL,
    pharm_class_epc TEXT
);

-- Where the data came from. The page shows it.
CREATE TABLE load_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- How long each step of the last load took.
CREATE TABLE pipeline_timings (
    step    TEXT NOT NULL,
    seconds DOUBLE PRECISION NOT NULL,
    rows    BIGINT
);
