---
marp: true
paginate: true
size: 16:9
title: Drug explorer
footer: "Drug explorer, Group D"
---

<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600;700&display=swap');
:root {
  --blue: #2450f0;
  --blue-deep: #1a37b0;
  --blue-soft: #e8edfe;
  --ink: #14171f;
  --ink-2: #3a3f4c;
  --muted: #5b6172;
  --paper: #f9fafc;
  --paper-2: #f0f2f7;
  --rule: #d5d9e2;
  --display: "Barlow Condensed", "Arial Narrow", sans-serif;
}
section {
  font-family: "Barlow", Helvetica, Arial, sans-serif;
  font-size: 25px;
  line-height: 1.4;
  padding: 64px 72px 70px 72px;
  color: var(--ink);
  background: var(--paper);
  justify-content: flex-start;
  place-content: start stretch;
}
/* blue band on top of every slide */
section::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 10px;
  background: var(--blue);
}
/* page number and footer */
section::after {
  font-family: var(--display); font-weight: 800; font-size: 20px;
  color: var(--blue); right: 72px; bottom: 26px; letter-spacing: 0.04em;
}
footer {
  font-family: var(--display); font-weight: 700; font-size: 15px;
  text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted);
  left: 72px; bottom: 28px;
}
.kicker {
  font-family: var(--display); font-weight: 700; font-size: 18px;
  text-transform: uppercase; letter-spacing: 0.16em; color: var(--blue);
  margin: 0 0 6px 0;
}
h1 {
  font-family: var(--display);
  font-weight: 800;
  font-size: 54px;
  line-height: 1.02;
  text-transform: uppercase;
  letter-spacing: -0.005em;
  margin: 0 0 30px 0;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--rule);
  color: var(--ink);
  position: relative;
}
h1::after {
  content: ""; position: absolute; left: 0; bottom: -2px;
  width: 110px; height: 6px; background: var(--blue);
}
strong { font-weight: 600; }
code { font-family: Menlo, "DejaVu Sans Mono", monospace; font-size: 0.82em; background: var(--paper-2); color: var(--ink); padding: 1px 6px; border-radius: 0; }

/* bullets: blue squares, like the app */
ul { margin: 0; padding: 0; list-style: none; }
ul > li { position: relative; padding-left: 28px; margin: 12px 0; }
ul > li::before { content: ""; position: absolute; left: 0; top: 0.55em; width: 10px; height: 10px; background: var(--blue); }
ol { margin: 0; padding: 0; list-style: none; counter-reset: step; }

img { display: block; }
.small { font-size: 17px; color: var(--muted); line-height: 1.4; }
.n { font-family: var(--display); font-weight: 800; line-height: 0.95; color: var(--blue); display: block; letter-spacing: -0.005em; }

/* ---------- title ---------- */
section.title {
  background: var(--blue); color: #fff;
  justify-content: center; place-content: center stretch;
  padding: 64px 80px;
}
section.title::before { background: var(--ink); height: 10px; }
section.title .brand {
  position: absolute; top: 46px; left: 80px;
  font-family: var(--display); font-weight: 800; font-size: 22px;
  letter-spacing: 0.14em; text-transform: uppercase; color: #fff;
}
section.title .brand span { opacity: 0.6; font-weight: 700; }
section.title h1 {
  color: #fff; font-size: 104px; line-height: 0.95; border: 0; padding: 0;
  margin: 0 0 30px 0; max-width: 980px;
}
section.title h1::after { display: none; }
section.title .lead { font-size: 28px; max-width: 900px; color: #fff; margin: 0 0 34px 0; }
.search { display: flex; width: 640px; height: 62px; margin: 0 0 0 0; box-shadow: 0 0 0 2px #fff; }
.search .field { flex: 1; background: #fff; color: var(--ink); font-size: 26px; display: flex; align-items: center; padding: 0 22px; }
.search .field i { display: inline-block; width: 2px; height: 30px; background: var(--blue); margin-left: 3px; font-style: normal; }
.search .btn { background: var(--ink); color: #fff; font-family: var(--display); font-weight: 800; font-size: 22px; letter-spacing: 0.1em; display: flex; align-items: center; padding: 0 30px; }
section.title .credits {
  position: absolute; left: 80px; right: 80px; bottom: 44px;
  font-size: 18px; line-height: 1.5; color: rgba(255,255,255,0.82);
  border-top: 1px solid rgba(255,255,255,0.35); padding-top: 14px;
  }
section.title .credits b { color: #fff; font-weight: 600; }

section a.repo { display: inline-flex; align-items: center; gap: 14px; margin-top: 26px; color: #fff; text-decoration: none; font-size: 24px; font-weight: 500; }
a.repo .tagw, a.live .tagw { font-family: var(--display); font-weight: 800; font-size: 16px; letter-spacing: 0.12em; text-transform: uppercase; padding: 4px 10px; }
a.repo .tagw { background: #fff; color: var(--blue); }
a.repo { border-bottom: 2px solid rgba(255,255,255,0.5); padding-bottom: 4px; }
section a.live { display: flex; align-items: center; gap: 12px; margin: -6px 0 18px 0; padding: 12px 16px; background: var(--blue); color: #fff; text-decoration: none; font-size: 20px; font-weight: 600; }
a.live .tagw { background: #fff; color: var(--blue); }
a.live b { margin-left: auto; font-family: var(--display); font-size: 26px; }

section.end h1 { font-size: 150px; margin-bottom: 26px; }
.qbox { display: inline-block; align-self: flex-start; background: #fff; color: var(--blue); font-family: var(--display); font-weight: 800; font-size: 54px; text-transform: uppercase; letter-spacing: 0.01em; padding: 8px 28px 6px 28px; line-height: 1.1; }

/* ---------- stats ---------- */
.four { display: grid; grid-template-columns: repeat(4, 1fr); gap: 22px; margin: 0 0 34px 0; }
.stat { background: #fff; border-top: 4px solid var(--blue); padding: 18px 18px 18px 18px; font-size: 20px; line-height: 1.3; color: var(--ink-2); box-shadow: 0 1px 0 var(--rule); }
.stat .n { font-size: 64px; margin-bottom: 8px; }

/* ---------- figure frame ---------- */
.frame { background: #fff; border: 1px solid var(--rule); padding: 18px; }
.frame img { width: 100%; }
.frame.arch { width: fit-content; padding: 14px; }
.frame.arch img { width: auto; }
.center { display: flex; justify-content: center; }

/* ---------- columns ---------- */
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 44px; align-items: start; }
.shotcols { display: grid; grid-template-columns: 1.5fr 1fr; gap: 40px; align-items: start; }
.shot { background: #fff; border: 1px solid var(--rule); padding: 8px; box-shadow: 10px 10px 0 var(--blue-soft); }
.shot img { width: 100%; }
.label { font-family: var(--display); font-weight: 800; font-size: 26px; text-transform: uppercase; letter-spacing: 0.02em; margin: 0 0 12px 0; }

.steps { display: grid; gap: 14px; }
.step { display: grid; grid-template-columns: 54px 1fr; gap: 16px; align-items: start; background: #fff; border: 1px solid var(--rule); padding: 14px 18px; font-size: 22px; line-height: 1.35; }
.step .n { font-size: 54px; }

.cmd { background: var(--ink); color: #fff; font-family: Menlo, "DejaVu Sans Mono", monospace; font-size: 16px; padding: 12px 16px; white-space: nowrap; line-height: 1.55; margin: 0 0 18px 0; }
.cmd .p { color: #7f9bff; }
.cmd .c { color: #9aa3b5; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 0 0 14px 0; }
.pair .stat .n { font-size: 52px; }
.pair .stat { padding: 12px 16px; }
.tight li { margin: 6px 0; font-size: 20px; line-height: 1.3; }

.quote { font-family: var(--display); font-weight: 700; font-size: 36px; line-height: 1.1; border-left: 6px solid var(--blue); padding: 4px 0 4px 20px; margin: 0 0 22px 0; color: var(--ink); }
.warn { background: var(--ink); color: #fff; padding: 16px 20px; font-weight: 600; margin-top: 22px; display: flex; gap: 14px; align-items: center; }
.warn .ico { font-family: var(--display); font-weight: 800; background: var(--blue); color: #fff; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: 26px; flex: none; }

/* ---------- table ---------- */
table { display: table; font-size: 21px; border-collapse: collapse; width: 100%; margin-top: -6px; }
th, td { padding: 8px 14px; border: 0 !important; border-bottom: 1px solid var(--rule) !important; text-align: right; background: transparent !important; font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; }
thead th { border-bottom: 2px solid var(--ink) !important; font-family: var(--display); font-weight: 800; font-size: 22px; text-transform: uppercase; letter-spacing: 0.04em; }
tr { background: transparent !important; }
section.measure td:last-child, section.measure th:last-child { background: var(--blue-soft) !important; font-weight: 600; }
section.measure tbody tr:nth-child(5) td { color: var(--blue); font-weight: 700; }
section.measure tbody tr:nth-child(6) td:not(:first-child) { color: var(--muted); }

section.who table { font-size: 25px; margin-top: 4px; }
section.who th, section.who td { text-align: left; padding: 10px 18px; }
section.who thead th { color: #fff; background: var(--blue) !important; border-bottom: 0 !important; font-size: 22px; }
section.who td:first-child { font-family: var(--display); font-weight: 800; font-size: 27px; text-transform: uppercase; color: var(--ink); width: 38%; letter-spacing: 0.01em; }
section.who tbody tr:nth-child(even) td { background: var(--blue-soft) !important; }
section.who .closing { margin-top: 26px; }
section.who .closing .q { font-size: 52px; }

/* ---------- cards ---------- */
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.card { background: #fff; border: 1px solid var(--rule); border-top: 4px solid var(--blue); padding: 20px 24px; font-size: 21.5px; line-height: 1.38; color: var(--ink-2); }
.card .n { font-size: 54px; margin-bottom: 8px; }
.card .n small { font-size: 22px; color: var(--muted); font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; margin-left: 6px; }

.versions { display: grid; grid-template-columns: 1fr 64px 1fr; align-items: stretch; margin-bottom: 18px; }
.ver { padding: 24px 28px; font-size: 23.5px; line-height: 1.38; }
.ver.old { background: var(--paper-2); color: var(--ink-2); border-top: 4px solid #9aa1b1; }
.ver.new { background: #fff; border: 1px solid var(--rule); border-top: 4px solid var(--blue); }
.ver .tag { font-family: var(--display); font-weight: 800; font-size: 30px; text-transform: uppercase; letter-spacing: 0.03em; margin: 0 0 4px 0; color: var(--ink); }
.ver .n { font-size: 68px; margin: 0 0 10px 0; }
.ver.old .n { color: #8a91a3; }
.ver .n small { font-size: 22px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-left: 6px; }
.ver li { margin: 10px 0; }
.ver.old li::before { background: #9aa1b1; }
.arrow { display: flex; align-items: center; justify-content: center; font-family: var(--display); font-weight: 800; font-size: 48px; color: var(--blue); }

.issues { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.issue { background: #fff; border: 1px solid var(--rule); padding: 16px 20px; font-size: 19.5px; line-height: 1.34; color: var(--ink-2); display: flex; flex-direction: column; }
.issue h3 { font-family: var(--display); font-weight: 800; font-size: 26px; line-height: 1.1; text-transform: uppercase; color: var(--ink); margin: 6px 0 8px 0; letter-spacing: 0.01em; }
.chip { display: inline-block; font-family: var(--display); font-weight: 800; font-size: 15px; letter-spacing: 0.12em; text-transform: uppercase; padding: 3px 10px; align-self: flex-start; }
.chip.ok { background: var(--blue); color: #fff; }
.chip.no { background: var(--ink); color: #fff; }
.delta { font-family: var(--display); font-weight: 800; font-size: 31px; color: var(--blue); margin-top: auto; padding-top: 8px; }

.team { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-top: 6px; }
.person { background: #fff; border: 1px solid var(--rule); padding: 18px 16px 20px 16px; font-size: 19px; line-height: 1.32; color: var(--ink-2); }
.person .ini { width: 64px; height: 64px; background: var(--blue); color: #fff; font-family: var(--display); font-weight: 800; font-size: 30px; display: flex; align-items: center; justify-content: center; margin-bottom: 16px; }
.person.me .ini { background: var(--ink); }
.person .name { font-family: var(--display); font-weight: 800; font-size: 25px; line-height: 1.02; text-transform: uppercase; color: var(--ink); margin-bottom: 10px; }
.closing { margin-top: 44px; display: flex; align-items: baseline; gap: 24px; }
.closing .q { font-family: var(--display); font-weight: 800; font-size: 64px; text-transform: uppercase; color: var(--blue); line-height: 1; }
.closing .u { font-size: 22px; color: var(--muted); }
</style>

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _footer: "" -->

<div class="brand">Drug explorer</div>

# Which drugs treat this condition?

<p class="lead">Drug explorer. You type a condition, we list the active ingredients whose FDA label names it.</p>

<div class="search"><div class="field">migraine<i></i></div><div class="btn">SEARCH</div></div>

<a class="repo" href="https://github.com/giulicastelli/drug-explorer/tree/main"><span class="tagw">Code</span>github.com/giulicastelli/drug-explorer</a>

<div class="credits"><b>Computing Infrastructures for Data Science, group D</b><br>Alessandro D'Amore, Andrea D'Ascanio, Federico Davolos, Giulia Castelli, Giovanni Margiacchi</div>

<!--
0:45, Giulia.
Our question is one a friend understands: which drugs treat this condition?
You type a condition, for example migraine. The page lists the active ingredients whose FDA label names migraine in the section "Indications and usage".
It only reads the labels, so it is not medical advice. We show where it breaks during the demo.
-->

---

<div class="kicker">The data</div>

# Every FDA drug label

<div class="four">
<div class="stat"><span class="n">1.87 GB</span>14 zip files from openFDA</div>
<div class="stat"><span class="n">264,748</span>labels in the export of 13 Nov 2026</div>
<div class="stat"><span class="n">84,381</span>labels we keep</div>
<div class="stat"><span class="n">CC0</span>public domain, no personal data</div>
</div>

- The loader downloads the zips by script. No key, no login.
- We keep a label only if it has a standard ingredient name and an indications text. The others cannot answer the question.
- For the measurements we load 25%, 50% and 100% of the kept labels.

<p class="small" style="margin-top:22px">The FDA publishes a new export every week. The measurements use the export of 18 Nov (84,576 labels kept), and the live demo uses the one on the laptop.</p>

<!--
1:30, Alessandro.
The data is the openFDA drug label export: the labels that companies file with the FDA. 14 zip files, 1.87 gigabytes.
The licence is CC0, so anyone can use it, and there is no personal data in it.
There are about 265 thousand labels. Two in three are of no use to us: they have no standard ingredient name, or no indications text. We keep 84,381.
We chose openFDA because it was the most comprehensive source, with the most data available, and that made the work simpler.
-->

---

<div class="kicker">Architecture</div>

# Three containers, one command

<div class="center"><div class="frame arch">

![h:380](../docs/architecture.png)

</div></div>

<!--
1:30, Giulia.
docker compose up starts three containers, in order.
The database starts first. The loader waits until it is ready, downloads the zips, keeps the usable labels and loads them. Then it stops.
The page starts only after the loader has finished, so nobody sees a half-empty database.
The zips stay in a folder on the laptop and the database in a volume, so the second start is fast.
-->

---

<div class="kicker">The database</div>

# Why PostgreSQL

<div class="cols">
<div>

<div class="label">Not MongoDB</div>

- The raw labels are nested JSON. That points to MongoDB.
- But we keep 13 fields of each label, so every row has the same columns.
- The work is counting labels per ingredient. That is SQL.
- PostgreSQL has the word search the question needs.

</div>
<div>

<div class="label">One search is one query</div>

<div class="steps">
<div class="step"><span class="n">1</span><div>PostgreSQL stores the stemmed words of each indications text: "migraines" becomes "migrain".</div></div>
<div class="step"><span class="n">2</span><div>A GIN index says which labels contain a word.</div></div>
<div class="step"><span class="n">3</span><div>The query finds the labels, counts them per ingredient and returns the top 25.</div></div>
</div>

</div>
</div>

<!--
1:30, Andrea.
Which database? The raw data is JSON, and we first thought of MongoDB.
But after cleaning, every label has the same 13 fields, and the work is to group and count. That is what SQL does well.
PostgreSQL also has full-text search. It stores the words of each text in a reduced form and builds an index on them, like the index at the back of a book.
So one search is one SQL query.
-->

---

<div class="kicker">Live demo</div>

# Demo: "migraine"

<div class="shotcols">
<div class="shot">

![](img/migraine.png)

</div>
<div>

<div class="cmd"><span class="p">$</span> docker compose up<br><span class="c"># then</span> localhost:8080</div>

<a class="live" href="https://drug-explorer-xi.vercel.app"><span class="tagw">Live</span>drug-explorer-xi.vercel.app <b>→</b></a>

<div class="pair">
<div class="stat"><span class="n">51</span>ingredients</div>
<div class="stat"><span class="n">752</span>labels</div>
</div>

<ul class="tight">
<li>First: topiramate, 146 labels</li>
<li>Prescription or over the counter</li>
<li>Suggestions while you type</li>
<li>Select an ingredient to read what its labels say</li>
</ul>

</div>
</div>

<!--
3:00 for slides 5 and 6, Federico, live. This slide and the next are the backup if the laptop fails.
Show the terminal: docker compose up, the three containers, the loader that finishes.
Open localhost:8080. Type migraine.
51 active ingredients, in 752 labels. The first is topiramate, with 146 labels.
Switch to "over the counter": the list changes to the ones you can buy without a prescription.
Select topiramate: the page shows the sentence of each label that names migraine.
-->

---

<div class="kicker">The limit</div>

# Where it breaks: "cancer"

<div class="shotcols">
<div class="shot">

![](img/cancer.png)

</div>
<div>

<p style="margin:0 0 10px 0">The first results are sunscreens. Their labels say:</p>

<div class="quote">"decreases the risk of skin cancer"</div>

<p style="margin:0">The search finds the word. It does not know whether the drug <strong>treats</strong> the condition or <strong>prevents</strong> it.</p>

<div class="warn"><span class="ico">!</span>Do not use it as medical advice.</div>

</div>
</div>

<!--
Still the demo. Type cancer.
The first results are zinc oxide and sunscreen filters. Not what you expect.
Their labels say "decreases the risk of skin cancer". The word is there, so the search finds them.
This is the limit of the project. We find a word in a text. We do not know whether the drug treats the condition or prevents it.
-->

---

<!-- _class: measure -->

<div class="kicker">Results</div>

# Measurements

| | 25% | 50% | 100% |
|---|---|---|---|
| Labels loaded | 21,107 | 42,107 | 84,576 |
| Load, later start | 3.0 s | 5.0 s | 8.4 s |
| Load, first start | 35.9 s | 37.6 s | 41.2 s |
| `up` until the page answers, later start | 7.9 s | 10.0 s | 13.2 s |
| "migraine" query, with the index | 0.9 ms | 0.8 ms | 0.7 ms |
| "migraine" query, without the index | 8.2 ms | 19.4 ms | 33.8 ms |
| Peak memory: loader / db / app (MiB) | 200 / 61 / 41 | 218 / 76 / 41 | 283 / 121 / 41 |
| Database on disk | 44 MB | 78 MB | 147 MB |

<p class="small" style="margin-top:14px">MacBook Pro, Apple M2 Pro, 32 GB of RAM. Docker had 12 CPUs and 7.75 GiB. Mean of 3 runs, each on an empty database. The zips were already on disk. Runs of 18 Nov, on the export of that day.</p>

<!--
1:00, Giovanni.
We measured at three sizes, three runs each, on one laptop, always from an empty database.
Time to load, time of a query, memory of each container, and the size on disk.
The next slide says what the numbers mean.
-->

---

<div class="kicker">Results</div>

# What the numbers mean

<div class="grid2">
<div class="card"><span class="n">2.8×<small>for 4× the labels</small></span>Loading grows more slowly than the data. With 4 times the labels it takes about 2.8 times as long.</div>
<div class="card"><span class="n">33 s<small>to read the zips</small></span>The first start is as slow with a quarter of the data as with all of it. Reading the 14 zips takes about 33 s whatever we keep. That is why we save the kept rows in a CSV.</div>
<div class="card"><span class="n">&lt; 1 ms<small>with the index</small></span>With the index a search takes under a millisecond at every size. Without it the time doubles when the data doubles, and at 100% it is about 49 times slower.</div>
<div class="card"><span class="n">147 MB<small>on disk</small></span>It all fits on a normal laptop. The loader peaks at 283 MiB and the database is 147 MB, 7.9% of the zips.</div>
</div>

<!--
2:00, Giovanni.
First: loading. Four times the data takes less than three times the time. Most of it is PostgreSQL storing the rows.
Second, the surprise. On the first start the time is almost the same at every size, because the loader has to read all the zips before it can keep a part. We come back to this in a moment.
Third: the index. With the index a search takes under a millisecond, whatever the size. Without it PostgreSQL reads every row, so the time grows with the data.
Fourth: it is small. Everything runs in a few hundred megabytes.
-->

---

# We built it twice

<div class="versions">
<div class="ver old">
<div class="tag">First version</div>
<span class="n">549<small>lines of loader</small></span>
<ul>
<li>A Streamlit page and a loader of 549 lines.</li>
<li>It worked, and we measured it three times.</li>
<li>Going through it for today, we found wrong results, and code that not all of us could explain.</li>
</ul>
</div>
<div class="arrow">→</div>
<div class="ver new">
<div class="tag">This version</div>
<span class="n">238<small>lines of loader</small></span>
<ul>
<li>The search leaves out "not indicated" sentences.</li>
<li>The loader is 238 lines and does the same job.</li>
<li>The page is plain HTML on a small server, and it is online.</li>
</ul>
</div>
</div>

<!--
1:00, Alessandro.
We want to say this openly. What you see today is the second version.
The first one worked. It had a Streamlit page and a long loader, and we had measured it three times.
When we went through it for this presentation we found two problems. Some results were wrong, the next slide shows which. And the loader had grown so much that not all of us could explain every part.
So we changed our mind and rebuilt it in two days. Each of us redid the part they own, in a separate pull request.
The old measurements no longer describe the code, so we measured again. We kept the old ones in the repo.
-->

---

# What went wrong

<div class="issues">
<div class="issue"><span class="chip ok">Fixed</span><h3>A quarter of the data took as long as all of it</h3>The loader read all 14 zips and then threw away three labels in four. Now it saves the kept rows after the first read.<div class="delta">46.1 s → 13.2 s <span class="small">start at 100%</span></div></div>
<div class="issue"><span class="chip ok">Fixed</span><h3>A good download was refused</h3>We compared each zip with the size in the FDA's file list, and that list is off by up to 0.16 MiB. Now the loader compares the bytes it receives with the size the server announces.</div>
<div class="issue"><span class="chip ok">Fixed</span><h3>ADHD drugs came up under "psychosis"</h3>Their labels say "not intended for" children with psychosis. Now we cut from "not indicated" to the end of the sentence.<div class="delta">64 → 2 <span class="small">labels</span></div></div>
<div class="issue"><span class="chip no">Not fixed</span><h3>"Cancer" finds sunscreens</h3>We did not fix this one. A word search cannot tell "treats" from "prevents", so we say it on the page.</div>
</div>

<!--
0:50 Alessandro (points 1 and 2), then 0:55 Andrea (points 3 and 4).
One. A quarter of the data took as long as all of it. The loader read every zip and threw away three labels in four. Now it saves the kept rows, and a start at 100% went from 46 to 13 seconds.
Two. The sizes in the FDA's file list are off by up to 0.16 MiB, so a good download was refused. We removed that check. Now the loader compares the bytes it receives with the size the server announces.
Three. ADHD drugs under "psychosis". A small SQL function cuts the "not indicated" sentences before indexing. 64 labels became 2.
Four. The sunscreens under "cancer". A word search cannot tell treating from preventing, so we say it on the page.
-->

---

<!-- _class: who -->

<div class="kicker">The team</div>

# Who did what

| Who | Part |
|---|---|
| Alessandro D'Amore | Getting the data and loading it |
| Andrea D'Ascanio | The database: tables, index, queries |
| Federico Davolos | The page: processing and the final output |
| Giulia Castelli | Docker, the README, the diagram |
| Giovanni Margiacchi | Measurements |

<!--
1:00. Each of us says one sentence on their own part, in the order of the table.
Then questions.
-->

---

<!-- _class: title end -->
<!-- _paginate: false -->
<!-- _footer: "" -->

<div class="brand">Drug explorer</div>

# Thank you!

<div class="qbox">Questions?</div>

<div class="credits"><b>Computing Infrastructures for Data Science, group D</b><br>Alessandro D'Amore, Andrea D'Ascanio, Federico Davolos, Giulia Castelli, Giovanni Margiacchi</div>

<!--
Giulia: "Thank you. We are happy to answer your questions."
-->
