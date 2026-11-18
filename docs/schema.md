# Schema

The source is `sql/schema.sql` (tables), `sql/indexes.sql` (the GIN index) and `sql/queries.sql` (the `drugs` table and the queries). This page explains why they look the way they do. Sizes are from the core test (`docs/evidence/core_pipeline_timings_*.txt`, one run each, not a benchmark).

## The four steps of the design

| Step | What we did |
|---|---|
| 1, Find the things | Two nouns in the question: a **label** (one FDA product label: a company's text for one product) and an **ingredient** (what the user wants back: "topiramate", or a combination like "acetaminophen + aspirin + caffeine"). One table each: `labels`, `drugs`. |
| 2, Name each row | `labels.set_id`: the FDA's id of a label and all its versions, unique in the export (262,907 distinct of 262,907, `docs/evidence/fp_sample.md` section 4), so it is the primary key. `drugs.substance_key`: the sorted, upper-case ingredient names joined with " + ", unique by construction (`GROUP BY`). |
| 3, Connect them | `labels.substance_key` → `drugs.substance_key`: one ingredient, many labels (zinc oxide: 1,840 at 100%). The link is by value; it is not declared as a foreign key (see "No foreign key" below). |
| 4, Store each fact once | What belongs to an ingredient (its number of labels, Rx and OTC, its most common class) is computed once into `drugs`; what belongs to a label (brand, manufacturer, date, text) stays in `labels`. |

```
labels  (set_id PK, label_id, version, effective_date, product_type, substance_key,
         generic_name, brand_name, manufacturer, route, pharm_class_epc, bucket,
         indications, tsv GENERATED)                    19,546 rows at 25%, 78,472 at 100% (export of 5 Nov; 84,363 at 100% in the export of 17 Nov, README)
   n ── 1   (by value: labels.substance_key = drugs.substance_key)
drugs   (substance_key PK, n_labels, n_rx, n_otc, pharm_class_epc)    3,554, 8,157 rows
```
Bookkeeping, as in the template: `pipeline_timings` (every step of every loader run, with its time, rows and a detail text) and `load_info` (source, licence, export date, sample fraction, counts).

## Columns of `labels`

| Column | Type | From the JSON | Why this way |
|---|---|---|---|
| `set_id` | `UUID` | `set_id` | 16 bytes instead of 36 characters; the database refuses a value that is not a UUID ("declare a column as a date, and the database will refuse anything that is not one"). |
| `label_id`, `version` | `TEXT`, `INTEGER` | `id`, `version` | Which version of the label this is. |
| `effective_date` | `DATE` | `effective_time` ("20250829") | A date, not text. One value is not a date: stored NULL and counted (D-8). |
| `product_type` | `TEXT` | `openfda.product_type[0]` | "Rx", "OTC", or the FDA's word in title case ("Cellular Therapy", 18 labels). |
| `substance_key` | `TEXT` | sorted `openfda.substance_name[]`, else `openfda.generic_name[]` | The ingredient the answer is grouped by (D-8). |
| `generic_name`, `brand_name`, `manufacturer` | `TEXT` | first value of the `openfda` list | Shown in the drill-down. |
| `route`, `pharm_class_epc` | `TEXT` | all values of the list, joined with "; " | Shown, never searched or grouped. Class present on 29.3% of rows. |
| `bucket` | `SMALLINT` | `md5(set_id)` mod 4 | Which sample a row belongs to (D-2): stored so a reader can check it. |
| `indications` | `TEXT` | `indications_and_usage[]`, whitespace normalised | The text the question searches. Median 898 characters for Rx, 125 for OTC (measured in the research step of 5 Nov 2026, outside the repository; not reproduced in `docs/evidence/`). |
| `tsv` | `TSVECTOR`, `GENERATED ALWAYS AS (to_tsvector('english', indications)) STORED` | – | The words of `indications`, stemmed, without stop words, with their positions ("migraines" → `migrain`). Computed once when the row is written, stored on disk, so no query recomputes it (D-9). |

Row storage: PostgreSQL stores a row's fields together. A value longer than about 2 kB (a long Rx indications text, and its `tsv`) is compressed and moved to a side table, the **TOAST** table, and the row keeps a pointer. At 100%: heap 71.8 MB, GIN 11.5 MB, primary key 3.3 MB, and the remaining 40.6 MB of `pg_total_relation_size('labels')` (127.2 MB) is TOAST plus small free-space and visibility maps (arithmetic on `core_pipeline_timings_100pct.txt`).

## The index

`labels_tsv_gin ON labels USING gin (tsv)` (`sql/indexes.sql`). GIN is an **inverted** index: for every lexeme (`migrain`, `epilepsi`), the list of rows that contain it. A phrase query ("type 2 diabetes" → `'type' <-> '2' <-> 'diabet'`) reads the lists of its words and checks the positions in the rows found. The planner uses it by itself: `Bitmap Index Scan on labels_tsv_gin`, 160 rows, 157 heap blocks at 25% (`docs/evidence/core_queries_25pct.txt`).

It is built after COPY, on the finished table (D-10): 0.30-0.46 s and 3.4 MB at 25%, 1.49 s and 11.5 MB at 100%. "one more copy of your data, kept in the order that answers a particular question. It speeds up reads, slows down writes, and takes disk space". Here the trade is clear: 11.5 MB and 1.5 s once, against 1.3 ms instead of 3,266 ms per query at 100% (D-11).

There is no index on `substance_key`: the drill-down first finds the condition's labels through the GIN index (hundreds of rows), then filters them by ingredient. `drugs.substance_key` has its primary key, which the join uses at 100% (`Index Scan using drugs_pkey`, `core_queries_100pct.txt`).

## Choices inside the schema

- **One wide table, flattened on purpose.** In the JSON, `openfda` holds lists: several substance names, routes, brand names, classes per label. A fully normalised design would have `label_substance`, `label_route`, `label_class` tables (many-to-many, "a third table holding pairs of keys"). We keep one row per label because the question groups by the **whole combination** (a three-ingredient pill is one answer), and the other lists are only shown, never searched. Cost: a search for "aspirin" as an ingredient alone would need that third table. Judgement: right for this question; it would be the first change for "which products contain aspirin?".
- **No foreign key from `labels` to `drugs`.** `drugs` is not loaded from a source: it is computed from `labels` by one `GROUP BY` after COPY (`sql/queries.sql`, name `drugs`), and both tables are emptied together (`TRUNCATE labels, drugs`). Every `substance_key` in `labels` is in `drugs` by construction. A foreign key would need `drugs` to exist before COPY, which is impossible here, or be added after, where it would check a rule that cannot fail. Measured cost in the template, for comparison only: a per-row key check was 80% of its COPY (template D-21).
- **Only `drugs` stores a class per ingredient.** An ingredient's labels can disagree on the class or not have one; `drugs.pharm_class_epc` is the most common non-empty one (`mode() WITHIN GROUP`), NULL when no label has one.
- **No `CHECK` on `product_type`.** The FDA's list of product types is theirs to change; the loader maps the two we use and keeps anything else as delivered (D-8).

## Why PostgreSQL and not MongoDB

The **raw data** has the shape that suits NoSQL: "Records have different fields, or are nested, like JSON from a website." A label is one JSON document with 19 to 47 top-level sections (four labels read today, `docs/dataset_decision.md`), most of them lists of text, and the `openfda` block is a nested object of lists that 69.1% of labels do not have at all (181,724 of 262,907, `docs/evidence/fp_sample.md` section 4). If we kept whole labels and asked many different questions of their sections, MongoDB would be the better answer: store each label as it comes, no flattening, a text index on the indications.

We do not keep whole labels. The loader keeps 13 fields of the 29.8% of labels that can answer the question, and flattens the lists (above). After that, **every row has the same columns**, and the work is "reporting and aggregation": count labels per ingredient, Rx and OTC, top 25. PostgreSQL also has what the question needs in one place: English stemming, phrase queries (`phraseto_tsquery`), a snippet function (`ts_headline`), and a GIN index the planner chooses by itself. Judgement, not tested: MongoDB's text index would also work, with one text index per collection and no built-in snippet function (from MongoDB's documentation; not reproduced in `docs/evidence/`).

"A database is chosen for the shape of the data, not out of habit." The shape we chose to keep is flat; the decision to flatten is what makes PostgreSQL the right answer, and it is a decision we can defend: we throw away 70% of the labels and most of each label before the database sees it.

A middle way we rejected: one `JSONB` column with the whole label in PostgreSQL. The JSON of the usable labels alone would be about 2.6 GB (78,472 / 262,907 × 8.75 GB: arithmetic, a prediction, not measured), against 127 MB for the flat table with its index.
