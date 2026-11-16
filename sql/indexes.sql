-- The one index of the project: find the labels whose indications contain a word or a phrase
-- without reading the whole table.
-- GIN = an inverted index: for every lexeme ('migrain'), the list of rows that contain it.
-- A phrase query ("type 2 diabetes") reads the lists of its words and checks their positions.
-- Built after COPY (one pass over the finished table, not one update per row); its cost
-- is measured: build time and disk space (pg_relation_size).
CREATE INDEX IF NOT EXISTS labels_tsv_gin ON labels USING gin (tsv);
