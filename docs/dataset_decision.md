# Why openFDA drug labels

We started from the question, "which drugs treat this condition?", and looked for data that
could answer it.

We chose openFDA because it was the most comprehensive source, with the most data available, and that made the work simpler.

## What we looked at

The course asks for a dataset of a few GB at most, with a clear licence, that a script can
download without a login, and with no personal data.

| Dataset | Licence | Size | Why yes or no |
|---|---|---|---|
| openFDA drug labels | CC0 | 1.87 GB of zips, about 265,000 labels | Chosen |
| SIDER 4.1 | CC BY-SA 4.0 | 1,437 drugs | The indications are already coded, but it stops at 2015 and is too small to measure anything |
| EMA medicines table | no named licence | 2,754 rows | Too small |
| openFDA NDC directory | CC0 | 138,229 products | No indications text |
| AIFA drug registry | CC BY 4.0 | 160,264 packs | No indications text |
| ChEMBL | CC BY-SA 3.0 | 8,683 indication rows | Small, and the download failed twice |
| openFDA FAERS | CC0 | 108 GB | Too big, and it has the age, sex and weight of patients |

The labels also gave us two problems worth solving for this course. The JSON is too big to open
in one go, so the loader has to read it a label at a time. And the question is a search in long
texts, which is slow without an index and fast with one, so there is something to measure.

## What this data cannot tell

Two labels in three are left out. Of the 264,748 labels in the export of 13 Nov 2026, 84,381
have both a standard ingredient name and an indications text. Without the name we cannot group
a label with the others of the same drug, so we drop it.

A mention is not a treatment. The search finds the word wherever it is in the indications.
"Cancer" brings up sunscreens, because their labels say "decreases the risk of skin cancer".

We fixed one case of this. Labels also say what a drug is not for ("not indicated for the
treatment of hypertension"), and those labels came up for that condition. Now the words from
"not indicated" to the end of the sentence are left out of the search. A label that says no in
other words still gets through.

There are no synonyms. "High blood pressure" and "hypertension" give different lists.

We count labels, and many labels are the same drug sold by different companies. A high count
means many products. It does not mean a better drug.

Most labels do not say which class the drug belongs to. The page leaves it empty and does not guess.

The FDA publishes a new export every week, so the counts move. The page shows the export date.

The FDA itself says: "Do not rely on openFDA to make decisions regarding medical care."
