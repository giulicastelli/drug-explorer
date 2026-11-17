# Research evidence: the numbers behind the dataset limits

**Where this comes from.** Before this repository existed, a research step on 5 Nov 2026 downloaded the export and measured it, on the same VM but without Docker, outside the repository. Its summary was cited in our documents but is not in the repository, so this file copies the underlying numbers, unchanged, from the research files named in each section. Nothing here was re-run, except one count in section 4, which says so. Copied on 5 Nov 2026, after the review.

## 1. "cancer": 20 random matches, with the verdict on each

- **Source:** `work/fp_samples.json` (the 20 matches, drawn by `scripts/match.py` with `random.Random(42)` from all "cancer" matches) and `scripts/fp_rules.py` (`JUDGED`: the verdict on each match, hard-coded with its reasons).
- **How the matches were found:** a Python stand-in for PostgreSQL's search, with the same stop words, the Snowball English stemmer and phrases at consecutive positions. It found 6,792 "cancer" labels (`work/match_results.json`). Our database finds the same 6,792 at 100% (`docs/evidence/core_queries_100pct.txt:19`).
- **The verdict is a Judgement,** made by reading the text. "True" means the label says that the drug treats, relieves or prevents the condition itself.

| # | `set_id` | Ingredient (`substance_key`) | Type | True? | Words around "cancer" |
|---:|---|---|---|---|---|
| 0 | 1c237d5a-1663-e9a1-e063-6294a90a6a24 | AVOBENZONE + HOMOSALATE + OCTISALATE + OCTOCRYLENE | OTC | no | "decreases the risk of skin cancer & early skin aging" |
| 1 | 9132366b-b808-46c9-b167-c1900bc116b3 | PALONOSETRON HYDROCHLORIDE | Rx | no | "nausea and vomiting associated with ... moderately emetogenic cancer chemotherapy" |
| 2 | 8d170f6f-37d7-41ce-aae2-33307a6ef3ae | CISPLATIN | Rx | yes | "Advanced Bladder Cancer Cisplatin Injection is indicated as a single agent" |
| 3 | b5631d3e-4604-4363-8f20-11dfc5a4a8ed | ENFORTUMAB VEDOTIN | Rx | yes | "indicated for the treatment of adult patients with muscle invasive bladder cancer" |
| 4 | b1a9f76d-0cef-29da-e053-2995a90af34c | ZINC OXIDE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 5 | 8f50e91e-66a7-4fd4-888a-9f1986aa661c | ALLOPURINOL | Rx | no | "patients with leukemia, lymphoma and solid tumor malignancies who are receiving cancer therapy" |
| 6 | b746c24d-f775-4433-8519-49c3ec48ea0c | AVOBENZONE + OCTISALATE + OCTOCRYLENE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 7 | 95ca0d81-a0a8-441d-820e-cb6624018a15 | ONDANSETRON HYDROCHLORIDE | Rx | no | "nausea and vomiting associated with ... emetogenic cancer chemotherapy" |
| 8 | 59713657-a7ef-1aee-e063-6394a90a326e | ZINC OXIDE | OTC | no | "decreases the riskof skin cancer and early skinaging" |
| 9 | b72caf9b-46df-f30c-e053-2995a90a9b6d | ZINC OXIDE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 10 | 743f3d23-0f5c-4724-9f69-411c109506e1 | TITANIUM DIOXIDE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 11 | 4c903249-69e9-4168-a9d1-22e6c2c1eb22 | LEVOTHYROXINE SODIUM | Rx | yes (borderline) | "adjunct to surgery and radioiodine therapy in the management of ... thyroid cancer" |
| 12 | fe9146ec-b85d-43da-a391-377960f2c772 | AVOBENZONE + HOMOSALATE + OCTISALATE + OCTOCRYLENE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 13 | 88bd6dff-ba19-4f8f-9432-28398d24f1ab | AVOBENZONE + OCTINOXATE + OXYBENZONE | OTC | no | "decreases the risk of skin cancer and early aging" |
| 14 | 114c6ac8-b133-cd16-e063-6294a90ac4f9 | ZINC OXIDE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 15 | 10d401af-fd92-d82a-e063-6294a90a9f7f | ZINC OXIDE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 16 | 00c61d11-d6b7-4618-b6f6-2592dbcc8af7 | DOCETAXEL ANHYDROUS | Rx | yes | "microtubule inhibitor indicated for: • Breast Cancer (BC)" |
| 17 | 2984c64f-eaac-ecb6-e063-6394a90aeb12 | AVOBENZONE + HOMOSALATE + OCTISALATE + OCTOCRYLENE | OTC | no | "decreases the risk of skin cancer and early skin aging" |
| 18 | f86d2158-b078-3f74-e053-6394a90aa4b6 | ANASTROZOLE | Rx | yes | "Adjuvant treatment of postmenopausal women with ... early breast cancer" |
| 19 | ba9331ef-3744-4072-80a2-af95c6f7ee05 | AVOBENZONE + HOMOSALATE + OCTISALATE | OTC | no | "decreases the risk of skin cancer and early skin aging" |

**Result: 5 true and 15 false.** The 15 false ones are:

- 12 sunscreens: rows 0, 4, 6, 8-10, 12-15, 17 and 19.
- 2 antiemetics, "cancer chemotherapy": rows 1 and 7.
- 1 allopurinol, "receiving cancer therapy": row 5.

The quotes above are cut from the `context` field of `fp_samples.json`; "..." marks text we left out.

**How sure.** With n = 20, the 75% false rate is ±19 points at 95% (arithmetic: 1.96 × √(0.75 × 0.25 / 20) = 0.19).

**"pain", for comparison.** Same method: 3 of 20 matches were false (cyclobenzaprine twice, and clonazepam, where "chest pain" is a panic symptom). Source: `scripts/fp_rules.py` and `work/fp_rules.json`, `sample_eval.pain.none`.

## 2. One rule tried on the same 20 (the dashboard does not use it)

Rule: the condition must come within 8 words after a treatment word (indicated, treatment, relief, prevention, therapy and others; the list is in `scripts/fp_rules.py`, `TRIG`). Results from `work/fp_rules.json`:

| On the 20 "cancer" matches | kept | of them false | true matches kept |
|---|---:|---:|---:|
| no rule | 20 | 15 | 5 of 5 |
| rule: within 8 words after a treatment word | 6 | 1 | 5 of 5 |
| Rx only | 8 | 3 | 5 of 5 |
| first sentence only | 13 | 10 | 3 of 5 |

On all 78,472 labels, the rule keeps 1,285 of the 6,792 "cancer" labels. It also cuts true answers: epilepsy goes from 1,051 to 502 labels and rheumatoid arthritis from 1,890 to 1,222 (`counts`). We kept the plain search. The dashboard shows the matching words of each label (`ts_headline`), so the user can see which matches are false (D-11).

## 3. The research download

Source: `raw/download_log.csv` and `raw/download_stdout.txt`, written by `scripts/download.py`. This was the research script, not our loader, run from this VM's network on 5 Nov 2026. Each file was fetched in one attempt, with no retries.

| File | Bytes | Seconds | Records |
|---|---:|---:|---:|
| drug-label-0001-of-0014.json.zip | 136,837,503 | 6.39 | 20,000 |
| drug-label-0002 | 150,583,189 | 6.93 | 20,000 |
| drug-label-0003 | 142,718,578 | 6.65 | 20,000 |
| drug-label-0004 | 143,592,822 | 6.62 | 20,000 |
| drug-label-0005 | 131,391,019 | 6.24 | 20,000 |
| drug-label-0006 | 142,966,674 | 6.47 | 20,000 |
| drug-label-0007 | 148,116,043 | 6.76 | 20,000 |
| drug-label-0008 | 144,007,189 | 6.26 | 20,000 |
| drug-label-0009 | 131,452,993 | 6.10 | 20,000 |
| drug-label-0010 | 137,870,841 | 6.26 | 20,000 |
| drug-label-0011 | 149,632,459 | 6.69 | 20,000 |
| drug-label-0012 | 140,084,549 | 6.52 | 20,000 |
| drug-label-0013 | 135,313,153 | 6.37 | 20,000 |
| drug-label-0014 | 24,340,404 | 1.41 | 2,907 |
| **total** | **1,858,907,416** | **85.67** | **262,907** |

The totals are our arithmetic on the CSV. 85.67 s is the sum of the per-file times; `REPORT.md` rounds it to 85.7 s. That works out to 21.7 MB/s (arithmetic). The per-file rate in `download_stdout.txt` is 17.3-23.0 MB/s.

The loader's own download path fetched only `download.json` and partition 14 (D-7). In v2 it also fetched partition 14 again in a failure test (`docs/evidence/v2_corrupt_zip.txt`, case c1).

## 4. Coverage counts (the "69.1% without an `openfda` block")

Sources: `work/stats_pass1.json` (written by `scripts/extract.py`), `work/stats_pass2.json` (`scripts/build_table.py`) and `work/partition_coverage.txt` (`scripts/partition_coverage.py`).

| Count | Labels | Share |
|---|---:|---:|
| labels in the export | 262,907 | 100% |
| with an `openfda` block (`has_openfda`) | 81,183 | 30.9% |
| no `openfda` block (`product_type` "(missing)") | 181,724 | 69.1% |
| with a generic name and indications (usable) | 78,472 | 29.8% |
| usable, with a pharmacologic class (`has_ind_gn_epc`) | 22,964 | 29.3% of usable |
| distinct `set_id` / `set_id` seen more than once | 262,907 / 0 | |
| usable rows after collapsing identical (ingredient, type, indications) | 33,606 | |
| usable rows by type: OTC / Rx / Cellular Therapy | 45,062 / 33,392 / 18 | |
| bucket sizes 0 / 1 / 2 / 3 (`md5(set_id)` mod 4) | 19,546 / 19,496 / 19,684 / 19,746 | |

The shares are our arithmetic. The share of labels with a generic name varies by partition: 19.1% to 39.8% in partitions 1-13, and 75.5% in the small partition 14 (`partition_coverage.txt`). That is why the 25/50/100% samples are not chosen by file (D-2).

**Where the class is missing.** We checked `REPORT.md`'s list ourselves on 5 Nov 2026, counting rows of `work/labels_clean.csv` with a non-empty `pharm_class_epc`, in one Python pass. None of the labels of these ingredients has a class: GABAPENTIN (375 labels), LISINOPRIL (150), METOPROLOL SUCCINATE (159), METOPROLOL TARTRATE (176) and SUMATRIPTAN SUCCINATE (74). The 8 labels whose ingredient is plain "SUMATRIPTAN" all have one.

## 5. Query times on a local PostgreSQL, no Docker

Source: `work/pg_bench_stdout.txt`, written by `scripts/pg_bench.py` on PostgreSQL 16 on this VM, outside Docker. Each value is the median of 5 runs (`REPEAT = 5`). These are not this project's measurements: those are in `measure/results/` (v1) and `measure/results_v2/`.

| At 100% (78,472 rows), ms | `ILIKE` | on the fly | stored `tsv`, scan | stored `tsv`, GIN |
|---|---:|---:|---:|---:|
| migraine | 926.75 | 11,362.03 | 71.15 | 2.00 |
| hypertension | 642.45 | 11,033.88 | 83.33 | 6.51 |
| sunburn | 735.15 | 8,707.46 | 138.97 | 13.72 |
| range over the 10 conditions | 642.45-944.83 | 8,497.96-11,816.63 | 71.15-138.97 | 2.00-13.72 |

- **Table size at 100%:** 63.8 MB without `tsv`, 111.6 MB with it, and 122.6 MB with the GIN index.
- **`ILIKE` misses stems:** "depression" finds 858 labels with `ILIKE`, against 2,652 with full-text search.
