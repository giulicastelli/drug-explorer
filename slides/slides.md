---
marp: true
paginate: true
size: 16:9
title: Drug explorer
---

<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@800&family=Barlow:wght@400;500;600&display=swap');
section {
  font-family: "Barlow", Helvetica, Arial, sans-serif;
  font-size: 27px;
  line-height: 1.4;
  padding: 56px 72px;
  color: #14171f;
  background: #f9fafc;
  justify-content: flex-start;
  place-content: start stretch;
}
h1 {
  font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
  font-weight: 800;
  font-size: 50px;
  line-height: 1.05;
  text-transform: uppercase;
  margin: 0 0 26px 0;
  padding-bottom: 14px;
  border-bottom: 3px solid #14171f;
  color: #14171f;
}
strong { font-weight: 600; }
b.n { font-family: "Barlow Condensed", sans-serif; font-weight: 800; font-size: 76px; line-height: 1; color: #2450f0; display: block; }
table { display: table; font-size: 23px; border-collapse: collapse; width: 100%; }
th, td { padding: 8px 12px; border: 0 !important; border-bottom: 1px solid #d5d9e2 !important; text-align: right; background: transparent !important; }
th:first-child, td:first-child { text-align: left; }
thead th { border-bottom: 2px solid #14171f !important; font-weight: 600; }
tr { background: transparent !important; }
ul { margin: 0; padding-left: 1.1em; }
li { margin: 10px 0; }
img { display: block; }
.shot img { border: 1px solid #c9cedb; width: 100%; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: start; }
.shotcols { display: grid; grid-template-columns: 1.55fr 1fr; gap: 36px; align-items: start; }
.four { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin: 0 0 30px 0; }
.four div { padding: 18px 16px 0 0; }
.small { font-size: 20px; color: #4a5060; }
section.title { justify-content: center; place-content: center stretch; }
section.who td, section.who th { text-align: left; }
section.title h1 { font-size: 84px; border: 0; margin-bottom: 10px; }
section::after { font-size: 16px; color: #4a5060; }
</style>

<!-- _class: title -->
<!-- _paginate: false -->

# Which drugs treat this condition?

Drug explorer. You type a condition, we list the active ingredients whose FDA label names it.

<p class="small">Computing Infrastructures for Data Science, group D<br>
Alessandro D'Amore, Andrea D'Ascanio, Federico Davolos, Giulia Castelli, Giovanni Margiacchi</p>

<!--
1 minute.
Our question is one a friend understands: which drugs treat this condition?
You type a condition, for example migraine. The page lists the active ingredients whose FDA label names migraine in the section "Indications and usage".
It only reads the labels, so it is not medical advice. We show where it breaks during the demo.
-->

---

# The data: every FDA drug label

<div class="four">
<div><b class="n">1.87 GB</b>14 zip files from openFDA</div>
<div><b class="n">264,748</b>labels in the export of 13 Nov 2026</div>
<div><b class="n">84,381</b>labels we keep</div>
<div><b class="n">CC0</b>public domain, no personal data</div>
</div>

- The loader downloads the zips by script. No key, no login.
- We keep a label only if it has a standard ingredient name and an indications text. The others cannot answer the question.
- For the measurements we load 25%, 50% and 100% of the kept labels.

<!--
2 minutes.
The data is the openFDA drug label export: the labels that companies file with the FDA. 14 zip files, 1.87 gigabytes.
The licence is CC0, so anyone can use it, and there is no personal data in it.
There are about 265 thousand labels. Two in three are of no use to us: they have no standard ingredient name, or no indications text. We keep 84,381.
We chose openFDA because it was the most comprehensive source, with the most data available, and that made the work simpler.
-->

---

# Three containers, one command

![w:1080](../docs/architecture.png)

<!--
1 minute.
docker compose up starts three containers, in order.
The database starts first. The loader waits until it is ready, downloads the zips, keeps the usable labels and loads them. Then it stops.
The page starts only after the loader has finished, so nobody sees a half-empty database.
The zips stay in a folder on the laptop and the database in a volume, so the second start is fast.
-->

---

# Why PostgreSQL

<div class="cols">
<div>

- The raw labels are nested JSON. That points to MongoDB.
- But we keep 13 fields of each label, so every row has the same columns.
- The work is counting labels per ingredient. That is SQL.
- PostgreSQL has the word search the question needs.

</div>
<div>

**One search is one query**

1. PostgreSQL stores the stemmed words of each indications text: "migraines" becomes "migrain".
2. A GIN index says which labels contain a word.
3. The query finds the labels, counts them per ingredient and returns the top 25.

</div>
</div>

<!--
1 minute.
Which database? The raw data is JSON, and we first thought of MongoDB.
But after cleaning, every label has the same 13 fields, and the work is to group and count. That is what SQL does well.
PostgreSQL also has full-text search. It stores the words of each text in a reduced form and builds an index on them, like the index at the back of a book.
So one search is one SQL query.
-->

---

# Demo: "migraine"

<div class="shotcols">
<div class="shot">

![](img/migraine.png)

</div>
<div>

`docker compose up`
then http://localhost:8080

- **51** ingredients in **752** labels
- First: topiramate, 146 labels
- Prescription or over the counter
- Suggestions while you type
- Select an ingredient to read what its labels say

</div>
</div>

<!--
3 minutes for the demo, live. This slide and the next are the backup if the laptop fails.
Show the terminal: docker compose up, the three containers, the loader that finishes.
Open localhost:8080. Type migraine.
51 active ingredients, in 752 labels. The first is topiramate, with 146 labels.
Switch to "over the counter": the list changes to the ones you can buy without a prescription.
Select topiramate: the page shows the sentence of each label that names migraine.
-->

---

# Where it breaks: "cancer"

<div class="shotcols">
<div class="shot">

![](img/cancer.png)

</div>
<div>

The first results are sunscreens. Their labels say "decreases the risk of skin cancer".

The search finds the word. It does not know whether the drug treats the condition or prevents it.

Do not use it as medical advice.

</div>
</div>

<!--
Still the demo. Type cancer.
The first results are zinc oxide and sunscreen filters. Not what you expect.
Their labels say "decreases the risk of skin cancer". The word is there, so the search finds them.
This is the limit of the project. We find a word in a text. We do not know whether the drug treats the condition or prevents it.
-->

---

# Measurements

| | 25% | 50% | 100% |
|---|---|---|---|
| Labels loaded | 21,063 | 42,019 | 84,381 |
| Load, later start | 3.0 s | 5.0 s | 8.4 s |
| Load, first start | 35.9 s | 37.6 s | 41.2 s |
| `up` until the page answers, later start | 7.9 s | 10.0 s | 13.2 s |
| "migraine" query, with the index | 0.9 ms | 0.8 ms | 0.7 ms |
| "migraine" query, without the index | 8.2 ms | 19.4 ms | 33.8 ms |
| Peak memory: loader / db / app (MiB) | 200 / 61 / 41 | 218 / 76 / 41 | 283 / 121 / 41 |
| Database on disk | 44 MB | 78 MB | 147 MB |

<p class="small">MacBook Pro, Apple M2 Pro, 32 GB of RAM. Docker had 12 CPUs and 7.75 GiB. Mean of 3 runs, each on an empty database. The zips were already on disk.</p>

<!--
1 minute.
We measured at three sizes, three runs each, on one laptop, always from an empty database.
Time to load, time of a query, memory of each container, and the size on disk.
The next slide says what the numbers mean.
-->

---

# What the numbers mean

- Loading grows more slowly than the data. With 4 times the labels it takes about 2.8 times as long.
- The first start is as slow with a quarter of the data as with all of it. Reading the 14 zips takes about 33 s whatever we keep. That is why we save the kept rows in a CSV.
- With the index a search takes under a millisecond at every size. Without it the time doubles when the data doubles, and at 100% it is about 49 times slower.
- It all fits on a normal laptop. The loader peaks at 283 MiB and the database is 147 MB, 7.9% of the zips.

<!--
2 minutes.
First: loading. Four times the data takes less than three times the time. Most of it is PostgreSQL storing the rows.
Second, the surprise. On the first start the time is almost the same at every size, because the loader has to read all the zips before it can keep a part. We come back to this in a moment.
Third: the index. With the index a search takes under a millisecond, whatever the size. Without it PostgreSQL reads every row, so the time grows with the data.
Fourth: it is small. Everything runs in a few hundred megabytes.
-->

---

# What went wrong

- A quarter of the data took as long as all of it. The loader read all 14 zips and then threw away three labels in four. Now it saves the kept rows after the first read, and a start at 100% went from 46.1 s to 13.2 s.
- A good download was refused. We compared each zip with the size in the FDA's file list, and that list is off by up to 0.16 MiB. We took the check out.
- ADHD drugs came up under "psychosis". Their labels say "not intended for" children with psychosis. Now we cut from "not indicated" to the end of the sentence: 64 labels became 2.
- "Cancer" finds sunscreens. We did not fix this one. A word search cannot tell "treats" from "prevents", so we say it on the page.

<!--
2 minutes.
Three things went wrong.
One. Our first measurement at 25 percent took almost as long as at 100. We expected a quarter. The loader was reading every zip and throwing away three labels in four. We added a file with the kept rows, and later starts became five times faster.
Two. The FDA publishes a list of the files with their sizes. We used it to check the downloads. The sizes in the list are rounded and sometimes wrong, so a correct file was refused. We removed that check.
Three. The sunscreens. This one we could not fix with the tools of this course. We decided to show it instead of hiding it.
-->

---

<!-- _class: who -->

# Who did what

| Who | Part |
|---|---|
| Alessandro D'Amore | Getting the data and loading it |
| Andrea D'Ascanio | The database: tables, index, queries |
| Federico Davolos | The page |
| Giulia Castelli | Docker, the README, the diagram |
| Giovanni Margiacchi | Measurements |

<!--
2 minutes. Each of us says one sentence on their own part.
Then questions.
-->
