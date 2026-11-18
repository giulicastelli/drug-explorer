# The database

The tables are in `sql/schema.sql`, the index in `sql/indexes.sql`, the page's queries in
`sql/queries.sql`.

## Tables

`labels` has one row per FDA label. The key is `set_id`, the id the FDA gives to a label.

`drugs` has one row per active ingredient, or per combination of ingredients: "acetaminophen +
aspirin + caffeine" is one drug for us, because that is what the label is for. The loader fills
it with one `GROUP BY` over `labels` (`sql/drugs.sql`).

The two are linked by `substance_key`: the ingredient names of a label in upper case, sorted
and joined with " + ".

`load_info` and `pipeline_timings` are two small tables about the last load: where the data
came from and how long each step took. The page shows them at the bottom.

## Columns worth a word

| Column | Type | Note |
|---|---|---|
| `effective_date` | `DATE` | A real date, so "newest first" sorts correctly |
| `product_type` | `TEXT` | "Rx", "OTC", or the FDA's word for the few others |
| `indications` | `TEXT` | The text we search |
| `tsv` | `TSVECTOR` | The words of `indications` after stemming ("migraines" becomes "migrain"), without the "not indicated for" sentences. PostgreSQL computes it when the row is written |
| `bucket` | `SMALLINT` | 0 to 3, from a hash of `set_id`. The 25% sample is bucket 0, the 50% sample is buckets 0 and 1, so a label is always in the same sample |

## The index

```sql
CREATE INDEX labels_tsv_gin ON labels USING gin (tsv);
```

A GIN index keeps, for each word, the list of the rows that contain it, like the index at the
back of a book. A search for "migraine" reads one short list and leaves the table alone. We
build it after the rows are in. The README has the times with and without it.

## Things we decided

We keep one wide table. In the JSON a label has lists (ingredients, routes, brand names), and
the textbook design would give each list its own table. We did not, because the question
groups by the whole combination of ingredients and the other lists are only shown. The cost is
that aspirin inside a combination is a different drug from aspirin alone.

There is no foreign key from `labels` to `drugs`. `drugs` is computed from `labels`, so the key
is always there.

The "not indicated for" rule is a function in the database, `searchable()` in
`sql/schema.sql`. It is one regular expression that replaces the words from "not indicated"
(or recommended, approved, intended, used, for use) to the next full stop with "[...]". The
`tsv` column and the sentence shown on the page both go through it, so they cannot disagree.

The stemmed words are stored, so the search does not stem 84,000 texts every time. It makes
the load slower and the table bigger.

## Why not MongoDB

The raw labels are nested JSON and no two have the same sections, which is the textbook case
for a document database. But we do not keep the labels as they are. We keep 13 fields, the
same for every label, and then we count and rank. That is a table and SQL. PostgreSQL also has
the stemming, the phrase search and the index in one place.

If we had kept the whole labels to ask different questions of their sections, MongoDB would
have been the better fit.
