-- The three queries of the page. app/server.py splits this file into one query per name line below.
-- %(condition)s is what the user typed, %(product_type)s is 'all', 'Rx' or 'OTC'.
-- phraseto_tsquery stems the words like the tsv column and keeps their order.

-- name: drugs_for_condition
-- The 25 ingredients with the most labels that name the condition.
-- We count first and join drugs after, so the join touches 25 rows.
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
SELECT hits.*,
       drugs.n_labels AS n_labels_all_conditions,
       drugs.pharm_class_epc
FROM hits
JOIN drugs USING (substance_key)
ORDER BY hits.n_labels DESC, substance_key;

-- name: condition_summary
-- The four numbers at the top of the page.
SELECT count(*)                                     AS n_labels,
       count(DISTINCT substance_key)                AS n_ingredients,
       count(*) FILTER (WHERE product_type = 'Rx')  AS n_rx,
       count(*) FILTER (WHERE product_type = 'OTC') AS n_otc
FROM labels
WHERE tsv @@ phraseto_tsquery('english', %(condition)s)
  AND (%(product_type)s = 'all' OR product_type = %(product_type)s);

-- name: labels_for_drug
-- The newest 20 labels of one ingredient, with the sentence around the match.
-- ts_headline is slow, so it runs on the 20 rows and not on every match.
-- It reads searchable(indications), so a "not indicated for" sentence is never the one shown.
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
       ts_headline('english', searchable(indications), phraseto_tsquery('english', %(condition)s),
                   'MaxFragments=1, MinWords=10, MaxWords=35') AS snippet
FROM hits
ORDER BY effective_date DESC NULLS LAST, set_id;
