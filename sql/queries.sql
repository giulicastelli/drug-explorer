-- The queries that answer the question. The loader, the dashboard and the benchmark read
-- this file and split it on the "-- name:" lines, so every query is written once.
-- Read each one in the order the database works: FROM, WHERE, GROUP BY, SELECT.
-- Parameters: %(condition)s is the text the user typed ("migraine", "type 2 diabetes");
-- %(product_type)s is 'all', 'Rx' or 'OTC'; %(substance_key)s is one row of drugs_for_condition.
-- phraseto_tsquery applies the same English stemming as the stored tsv and keeps the word
-- order: 'type 2 diabetes' -> 'type' <-> '2' <-> 'diabet'.

-- name: drugs
-- Processing step, run once by the loader: one row per active ingredient (or combination)
-- with its number of labels, Rx and OTC, and the most common pharmacological class.
SELECT substance_key,
       count(*)                                     AS n_labels,
       count(*) FILTER (WHERE product_type = 'Rx')  AS n_rx,
       count(*) FILTER (WHERE product_type = 'OTC') AS n_otc,
       mode() WITHIN GROUP (ORDER BY pharm_class_epc)
           FILTER (WHERE pharm_class_epc IS NOT NULL) AS pharm_class_epc
FROM labels
GROUP BY substance_key;

-- name: drugs_for_condition
-- Q1, the main query: the 25 ingredients with the most labels whose indications mention the
-- condition. The GIN index finds the matching labels (no full scan); they are grouped
-- first, and only the 25 groups left are joined with drugs (reduce first, join after).
WITH hits AS (
    SELECT substance_key,
           count(*)                                     AS n_labels,
           count(*) FILTER (WHERE product_type = 'Rx')  AS n_rx,
           count(*) FILTER (WHERE product_type = 'OTC') AS n_otc
    FROM labels
    WHERE tsv @@ phraseto_tsquery('english', %(condition)s)
      AND (%(product_type)s = 'all' OR product_type = %(product_type)s)
    GROUP BY substance_key
    ORDER BY n_labels DESC, substance_key
    LIMIT 25
)
SELECT h.substance_key,
       h.n_labels,
       h.n_rx,
       h.n_otc,
       d.n_labels AS n_labels_all_conditions,   -- all its labels, whatever they treat
       d.pharm_class_epc
FROM hits h
JOIN drugs d ON d.substance_key = h.substance_key
ORDER BY h.n_labels DESC, h.substance_key;

-- name: condition_summary
-- Q2, the headline: how many labels and distinct ingredients mention the condition.
SELECT count(*)                                     AS n_labels,
       count(DISTINCT substance_key)                AS n_ingredients,
       count(*) FILTER (WHERE product_type = 'Rx')  AS n_rx,
       count(*) FILTER (WHERE product_type = 'OTC') AS n_otc
FROM labels
WHERE tsv @@ phraseto_tsquery('english', %(condition)s)
  AND (%(product_type)s = 'all' OR product_type = %(product_type)s);

-- name: labels_for_drug
-- Q3, the drill-down: the labels of one ingredient that mention the condition, newest first,
-- with a snippet of the text around the match. At most 20 rows; ts_headline re-reads the
-- whole indications text, so it runs only on the 20 rows returned, not on every match.
-- Same product-type filter as Q1, so its count matches the row picked in the table.
WITH hits AS (
    SELECT set_id, brand_name, manufacturer, effective_date, product_type, indications
    FROM labels
    WHERE tsv @@ phraseto_tsquery('english', %(condition)s)
      AND substance_key = %(substance_key)s
      AND (%(product_type)s = 'all' OR product_type = %(product_type)s)
    ORDER BY effective_date DESC NULLS LAST, set_id
    LIMIT 20
)
SELECT brand_name,
       manufacturer,
       effective_date,
       product_type,
       ts_headline('english', indications, phraseto_tsquery('english', %(condition)s),
                   'MaxFragments=1, MinWords=10, MaxWords=35') AS snippet,
       set_id
FROM hits
ORDER BY effective_date DESC NULLS LAST, set_id;

-- name: drugs_for_condition_on_the_fly
-- Q1 without the stored column, kept only for the measurements: the words of every label are
-- computed again for every query. No index can serve it (the GIN index is on tsv), so it
-- reads and re-stems every row: same answer as drugs_for_condition, much slower.
WITH hits AS (
    SELECT substance_key,
           count(*)                                     AS n_labels,
           count(*) FILTER (WHERE product_type = 'Rx')  AS n_rx,
           count(*) FILTER (WHERE product_type = 'OTC') AS n_otc
    FROM labels
    WHERE to_tsvector('english', indications) @@ phraseto_tsquery('english', %(condition)s)
      AND (%(product_type)s = 'all' OR product_type = %(product_type)s)
    GROUP BY substance_key
    ORDER BY n_labels DESC, substance_key
    LIMIT 25
)
SELECT h.substance_key,
       h.n_labels,
       h.n_rx,
       h.n_otc,
       d.n_labels AS n_labels_all_conditions,
       d.pharm_class_epc
FROM hits h
JOIN drugs d ON d.substance_key = h.substance_key
ORDER BY h.n_labels DESC, h.substance_key;
