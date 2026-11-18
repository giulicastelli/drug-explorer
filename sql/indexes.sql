-- For each word, the list of labels that contain it.
-- Without it every search reads all the rows.
CREATE INDEX labels_tsv_gin ON labels USING gin (tsv);
