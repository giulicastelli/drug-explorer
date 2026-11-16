# Dataset decision (Step 2)

The question was fixed first: **"Which drugs treat this condition?"** The user types a condition; the answer is the list of active ingredients whose FDA label names it under "Indications and usage", with the number of labels, Rx vs OTC, and the pharmacological class when known.

## In short, in our words

We chose openFDA because it was the most comprehensive source, with the most data available, and that made the work simpler.

Ten drug datasets were checked on 5 Nov 2026 by downloading the data on the cloud VM (and from the class notes "CI - dataset per atlante farmaci.md"). The openFDA NDC file was downloaded and read for this page. Facts come from pages fetched or commands run; anything not verified says so and is excluded from the winner. Scores 1-5 on nine criteria (a fit, b four data tests, c question, d database reason, e measurement richness, f fits ~3 containers, g defensible by five, h risk, inverse, i Italian/European angle). Criterion c is scored for **this** question: a dataset without indications cannot answer it.

## Verified facts

| # | Candidate | Download (no login) | Licence (quoted) | Size and rows (measured) | Personal data | Verdict |
|---|---|---|---|---|---|---|
| 1 | **openFDA drug labels** (`drug/label` bulk export) | manifest `https://api.fda.gov/download.json` → 14 zips at `https://download.open.fda.gov/drug/label/drug-label-00NN-of-0014.json.zip`, HTTP 200, no key | "the content, data, documentation, code, and related materials on openFDA is public domain and made available with a Creative Commons CC0 1.0 Universal dedication" (https://open.fda.gov/license/, saved page `drugatlas/adverse-events/dl/license.html`) | 262,907 labels, 1,858,907,416 bytes of zips (85.7 s), 8.75 GB of JSON inside; export of 2026-11-05 (research download and counts, copied into `docs/evidence/fp_sample.md` sections 3-4) | None: product labels of companies | **Winner** |
| 2 | SIDER 4.1 indications + side effects | `https://sideeffects.embl.de/download/` | "Except as otherwise noted, this work is licensed under a Creative Commons Attribution-Share Alike 4.0 License" (saved `sider/index.html`); drug names and ATC CC0 (class notes) | `meddra_all_indications.tsv.gz`: 30,835 rows, 1,437 drugs, 15,083 drug × indication pairs at MedDRA PT level; `meddra_all_se`: 309,849 rows (`zcat \| wc -l`, today) | None | Runner-up |
| 3 | EMA medicines table | `https://www.ema.europa.eu/en/documents/report/medicines-output-medicines-report_en.xlsx` | No named open licence: "may be reproduced and / or distributed... provided that EMA is always acknowledged as the source" (EMA legal notice) | 904,807 B, 2,754 rows (2,357 human medicines), indication text and MeSH areas | None | Runner-up |
| 4 | openFDA NDC directory | `https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip` → 200, 27,689,578 B in 1.8 s (today) | CC0, same page as #1 | 138,229 products, 242,575,346 B of JSON. Fields read today: `active_ingredients`, `pharm_class` (74,306 products), `product_type`, `route`, `brand_name`... **no indications field** | None | Out (cannot answer the question) |
| 5 | AIFA drug registry (Anagrafica Farmaci) | `https://drive.aifa.gov.it/farmaci/confezioni_fornitura.csv`, `PA_confezioni.csv`, `atc.csv` | "La licenza di distribuzione dei dati utilizzata da AIFA la CC-BY (attribuzione) nella versione 4.0" (site-wide, aifa.gov.it/open-data); licence on the files **not verified** | 160,264 packs, 339,482 pack × ingredient rows, 7,219 ATC rows | None | Out (no indications text; licence of the files not verified) |
| 6 | DrugCentral 2027 | `https://unmtid-dbs.net/download/DrugCentral/2027/drug.target.interaction.tsv.gz` | CC BY-SA 4.0 (drugcentral.org/privacy links the legal code) | target file 22,364 rows; the indications live in the full `.pgdump` (needs the RDKit extension), size **not verified** | None | Out (indications not verified, small) |
| 7 | ChEMBL 37 | REST API with no key; FTP reset the connection twice from the cloud VM | "Creative Commons Attribution-Share Alike 3.0 Unported License" (ChEMBL docs) | `drug_indication`: 8,683 rows (API total); bulk files **not verified** | None | Out (small, bulk download unreachable) |
| 8 | openFDA FAERS (`drug/event`) | same manifest as #1 | CC0 | 1,799 zips, 21,054,159 reports, 108,369.62 MB zipped (manifest, export 2026-11-02) | Patient age in 893 and sex in 1,136 of the 1,396 reports of one file; weight too | Out (50× over "a few GB"; individual health data) |
| 9 | OFFSIDES (nsides) | `https://tatonettilab-resources.s3.us-west-1.amazonaws.com/nsides/OFFSIDES.csv.gz` | **None stated** on tatonettilab.org, nsides.io or in README.txt | 3,206,558 rows, 68.8 MB gz | None | Out (no licence: a MUST) |
| 10 | WHO ATC/DDD index | "can be downloaded from a registered user account" (atcddd.fhi.no) | "Changing or manipulating the material is not allowed" | – | – | Out (login, no reuse) |

First rows read by hand (winner, `drug-label-0014-of-0014.json.zip`, today): label 1 nadolol, "indicated for the long-term management of patients with angina pectoris. Hypertension ...", **no `openfda` block**; label 2 a sunscreen, "helps prevent sunburn ... decreases the risk of skin cancer", **no `openfda` block**; label 3 miconazole nitrate, `openfda.product_type` HUMAN OTC DRUG, "treatment of most athlete's foot"; label 4 LYRICA, "Management of neuropathic pain", **no `openfda` block**. The four labels have 24, 22, 19 and 47 top-level fields. These four rows already show the two main limits below: three of them (nadolol, the sunscreen, LYRICA) have no harmonised name, and "cancer" appears in a sunscreen.

## Scores

| Candidate | a | b | c | d | e | f | g | h | i | Total |
|---|---|---|---|---|---|---|---|---|---|---|
| **openFDA drug labels** | 5 | 4 | 5 | 4 | 4 | 5 | 4 | 3 | 2 | **36** |
| AIFA registry | 4 | 3 | 1 | 4 | 4 | 5 | 5 | 3 | 5 | 34 |
| SIDER 4.1 | 3 | 4 | 5 | 3 | 1 | 5 | 5 | 2 | 3 | 31 |
| openFDA NDC | 3 | 5 | 1 | 3 | 3 | 5 | 5 | 4 | 1 | 30 |
| EMA medicines | 2 | 2 | 4 | 3 | 1 | 5 | 5 | 3 | 5 | 30 |
| ChEMBL 37 | 3 | 3 | 4 | 3 | 1 | 4 | 4 | 2 | 4 | 28 |
| DrugCentral | 3 | 4 | 2 | 4 | 2 | 4 | 4 | 3 | 1 | 27 |
| FAERS, OFFSIDES, WHO ATC | – | 1 | – | – | – | – | – | – | – | out on a MUST |

AIFA scores second in total but cannot answer the question (c = 1): it would be a different project. The two runners-up below are the two that **can** answer it.

One-line justifications for the winner (Judgement):
- **a** a script download, a database, one index whose effect is dramatic, three sizes: all five requirements arise naturally.
- **b** CC0 quoted, no key or login, 1.86 GB zipped is under "a few GB", first rows read by hand; not a 5 because the JSON inside is 8.75 GB, so it must be streamed (D-1).
- **c** "which drugs treat migraine?" is one sentence a friend understands; the answer is a ranking.
- **d** the question is a word search in long text, then a count per ingredient: full-text search with an inverted (GIN) index is a database feature with no CSV equivalent ("An index finds one customer among a billion in milliseconds. A CSV has to be read from beginning to end."). Not a 5: the source is nested JSON, which points to MongoDB first (see `docs/schema.md`).
- **e** 78,472 usable labels, a database of 41 MB at 25% and 138 MB at 100%: the index effect is huge (1.3 ms against 3,266 ms for stemming on the fly at 100%, D-11), but these are not millions of rows, and the parse does not shrink with the sample (D-3).
- **f** db, loader, app, nothing else.
- **g** Python, SQL, Streamlit; two things to learn: `tsvector` / GIN, and ijson (D-1). Not a 5.
- **h** coverage (30.9% of labels have harmonised names), false positives, a new export every week; the URLs are stable (one pattern for all 14 files).
- **i** a US agency; no Italian angle. The Italian AIFA registry was checked first and has no indications text.

## Why the runners-up lost

- **SIDER 4.1:** it already contains the answer, coded: one row per drug and MedDRA indication (30,835 rows, 1,437 drugs). The question becomes a lookup in a 30 k-row table, so no index or growth effect would rise above noise (e = 1). It is also from 21 Oct 2015 and says "intended for educational and scientific research purposes only". Judgement: SIDER's indications were themselves extracted from drug labels; we start one step earlier, from today's labels.
- **EMA medicines table:** it has the indication text, and a European angle, but only 2,754 rows, and the reuse terms are a legal notice, not a named open licence. Fails "a clear licence" as strictly read, and is too small to measure.

## Dropped, and why

- **Licence:** OFFSIDES and TWOSIDES (none stated), WHO ATC (no changes allowed), EMA (no named licence), AIFA (site-wide statement only).
- **Size:** FAERS, 108 GB zipped across 1,799 files.
- **Login:** WHO ATC (registered account). ChEMBL needs no login, but its bulk files could not be reached from the cloud VM.
- **Patient data:** FAERS reports carry age, sex and weight per patient; says "No personal or private data".
- **Cannot answer the question:** openFDA NDC and AIFA (no indications), DrugCentral (indications only in a dump we could not verify).

## Known limits of the winner (stated wherever the answer appears)

1. **Coverage.** Only 81,183 of 262,907 labels (30.9%) carry the `openfda` block with the harmonised names, product type and class; with a non-empty indications text, 78,472 (29.8%) are usable (research counts in `docs/evidence/fp_sample.md` section 4; loader counts in `docs/evidence/core_pipeline_timings_100pct.txt`). A label without the block (nadolol, the sunscreen and LYRICA above) cannot be grouped by ingredient, so it is not counted. The answer is "among labels with harmonised names", not "all FDA labels".
2. **A mention is not a treatment.** The search finds the condition anywhere in "Indications and usage". "Cancer" matches 6,792 labels at 100%, and the top three ingredients are sunscreens ("decreases the risk of skin cancer"); in 20 random matches, 15 were false, 12 of them sunscreens (the 20 `set_id`s with the verdict on each are in `docs/evidence/fp_sample.md` section 1; n = 20, ±19 points at 95%). "Pain": 3 of 20 false. Populations and risk factors also match ("type 2 diabetes" brings atorvastatin).
3. **The class is sparse.** The established pharmacologic class (EPC) exists for 22,964 of 78,472 usable labels (29.3%, `core_pipeline_timings_100pct.txt`); it is missing for every gabapentin, lisinopril and metoprolol label and for sumatriptan succinate (`docs/evidence/fp_sample.md` section 4; corrected after review: this said "sumatriptan", but the 8 plain "SUMATRIPTAN" labels have a class). The dashboard says "not in label data" instead of guessing.
4. **No synonyms.** "High blood pressure" does not find "hypertension"; "type II diabetes" does not find "type 2 diabetes".
5. **Repackagers.** Many labels are the same ingredient from different companies and repackagers (zinc oxide: 1,840 labels at 100%). We count labels per ingredient, which measures how many products exist, not how good a drug is.
6. **A new export every week.** Counts change; the loader stores `export_date` (2026-11-05) in `load_info`, and the cached files are reused with their own manifest (D-6).
7. **FDA's own warning** (manifest `meta.disclaimer`): "Do not rely on openFDA to make decisions regarding medical care ... you should assume all results are unvalidated." The dashboard says "Not medical advice".
