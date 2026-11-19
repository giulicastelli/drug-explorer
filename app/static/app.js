// The search is kept in the URL (?q=migraine&type=Rx&drug=SUMATRIPTAN),
// so a result can be sent as a link and the back button works.
const $ = (sel, root = document) => root.querySelector(sel);
const out = $("#out"), results = $("#results"), form = $("#search"), input = $("#q");
const NO_CLASS = "no class on the labels";
const TYPE_WORDS = { all: "", Rx: " Only prescription labels are counted.", OTC: " Only over the counter labels are counted." };
const nf = new Intl.NumberFormat("en-US");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const plural = (n, one, many) => (n === 1 ? one : many);
let ticket = 0; // a slow answer to an old search must not overwrite a newer one

function state() {
  const p = new URLSearchParams(location.search);
  const type = ["all", "Rx", "OTC"].includes(p.get("type")) ? p.get("type") : "all";
  return { q: (p.has("q") ? p.get("q") : "migraine").trim(), type, drug: p.get("drug") || "" };
}

function go(next, replace = false) {
  const s = { ...state(), ...next };
  const p = new URLSearchParams();
  p.set("q", s.q);
  if (s.type !== "all") p.set("type", s.type);
  if (s.drug) p.set("drug", s.drug);
  history[replace ? "replaceState" : "pushState"](null, "", "?" + p);
}

async function getJSON(path, params) {
  const res = await fetch(path + "?" + new URLSearchParams(params));
  if (!res.ok) throw new Error(`${path} answered ${res.status}`);
  return res.json();
}

function skeleton() {
  out.innerHTML = `<div class="skel skel--head"></div><div class="skel skel--board"></div>` +
    `<div class="skel skel--row"></div>`.repeat(8) + `<p class="visually-hidden">Searching the labels.</p>`;
}

function failed(retry) {
  out.innerHTML = `<div class="notice notice--error" role="alert"><h2>The database did not answer</h2>
    <p>It may still be starting. Wait a few seconds and try again.</p>
    <button class="btn btn--secondary" type="button" id="retry">Try again</button></div>`;
  $("#retry").addEventListener("click", retry);
}

function empty(q) {
  out.innerHTML = `<div class="notice"><h2>No label matches</h2>
    <p>No label names “${esc(q)}” in its indications. Try another word or a shorter phrase. The search looks for the words you typed, in the same order.</p></div>`;
}

function bar(d, max) {
  const other = d.n_labels - d.n_rx - d.n_otc;
  const seg = (n, cls) => (n ? `<i class="${cls}" style="width:${((n / max) * 100).toFixed(2)}%"></i>` : "");
  return `<div class="stack" role="img" aria-label="${d.n_rx} prescription, ${d.n_otc} over the counter, ${other} other">` +
    seg(d.n_rx, "s-rx") + seg(d.n_otc, "s-otc") + seg(other, "s-other") + `</div>`;
}

function draw(s, data) {
  const sum = data.summary, drugs = data.drugs;
  if (!s.q || sum.n_labels === 0) return empty(s.q);
  const other = sum.n_labels - sum.n_rx - sum.n_otc;
  const max = Math.max(...drugs.map((d) => d.n_labels));
  const fig = (n, label) => `<div><dt>${label}</dt><dd>${nf.format(n)}</dd></div>`;
  const rows = drugs.map((d, i) => {
    const cls = d.pharm_class_epc ? d.pharm_class_epc.replace(" [EPC]", "") : NO_CLASS;
    return `<tr data-key="${esc(d.substance_key)}">
      <td class="rank">${i + 1}</td>
      <td><button class="row-btn" type="button" aria-expanded="false" data-drug="${esc(d.substance_key)}" data-n="${d.n_labels}">
        <b>${esc(d.substance_key.toLowerCase())}</b><small>${esc(cls)}</small></button></td>
      <td class="barcell">${bar(d, max)}</td>
      <td class="num lead-num">${nf.format(d.n_labels)}</td>
      <td class="num" data-label="Rx">${nf.format(d.n_rx)}</td>
      <td class="num" data-label="OTC">${nf.format(d.n_otc)}</td>
      <td class="num" data-label="All its labels">${nf.format(d.n_labels_all_conditions)}</td></tr>`;
  }).join("");
  out.innerHTML = `
    <div class="results__head"><h2>Named for “${esc(s.q)}”</h2></div>
    <dl class="board">
      ${fig(sum.n_ingredients, plural(sum.n_ingredients, "active ingredient", "active ingredients"))}
      ${fig(sum.n_labels, plural(sum.n_labels, "FDA label", "FDA labels"))}
      ${fig(sum.n_rx, "prescription")}
      ${fig(sum.n_otc, "over the counter")}
      ${other ? fig(other, "other") : ""}
    </dl>
    <p class="meta">The database answered in ${(data.ms_drugs + data.ms_summary).toFixed(0)} ms.${TYPE_WORDS[s.type]}</p>
    <div class="ledger-head">
      <h3>The ingredients with the most labels</h3>
      <ul class="legend" aria-label="Label type"><li><i class="s-rx"></i>Rx</li><li><i class="s-otc"></i>OTC</li><li><i class="s-other"></i>other</li></ul>
    </div>
    <div class="scroll"><table class="ledger">
      <thead><tr><th scope="col"><span class="visually-hidden">Rank</span></th><th scope="col">Active ingredient and pharmacological class</th>
        <th scope="col">Labels that mention the condition</th><th scope="col" class="num">Labels</th><th scope="col" class="num">Rx</th>
        <th scope="col" class="num">OTC</th><th scope="col" class="num">All its labels</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    <p class="note">Top ${drugs.length} of ${nf.format(sum.n_ingredients)}. Select an ingredient to read what its labels say. “All its labels” counts every label of the ingredient, whatever it is for. Most labels do not give a drug class.</p>`;
  if (s.drug) open(s.drug, false);
}

function closeRow() {
  $(".said", out)?.remove();
  const tr = $("tr.is-open", out);
  if (tr) { tr.classList.remove("is-open"); $(".row-btn", tr).setAttribute("aria-expanded", "false"); }
}

async function open(drug, push = true) {
  const btn = [...out.querySelectorAll(".row-btn")].find((b) => b.dataset.drug === drug);
  if (!btn) return;
  const wasOpen = btn.getAttribute("aria-expanded") === "true";
  closeRow();
  if (wasOpen) { if (push) go({ drug: "" }); return; }
  if (push) go({ drug });
  const s = state(), tr = btn.closest("tr");
  tr.classList.add("is-open");
  btn.setAttribute("aria-expanded", "true");
  const panel = document.createElement("tr");
  panel.className = "said";
  panel.innerHTML = `<td colspan="7"><div class="said__in"><h4>What the labels say</h4><div class="skel skel--row"></div><div class="skel skel--row"></div></div></td>`;
  tr.after(panel);
  const box = $(".said__in", panel);
  try {
    const data = await getJSON("api/labels", { q: s.q, type: s.type, drug });
    if (!panel.isConnected) return;
    const items = data.labels.map((r) => {
      // PostgreSQL marks the matched words with <b>. Escape the text, then bring back only those tags.
      const snippet = esc(r.snippet).replaceAll("&lt;b&gt;", "<mark>").replaceAll("&lt;/b&gt;", "</mark>");
      const meta = [r.manufacturer || "", r.effective_date || "no date", r.product_type].filter(Boolean).join(", ");
      return `<li><b>${esc(r.brand_name || "(no brand name)")}</b> <span>, ${esc(meta)}</span><p>… ${snippet} …</p></li>`;
    }).join("");
    box.innerHTML = `<h4>What the labels say</h4>
      <p class="meta">${data.labels.length} of ${nf.format(+btn.dataset.n)} labels, newest first.${TYPE_WORDS[s.type]}</p>
      <ol aria-label="Label excerpts">${items}</ol>`;
  } catch {
    box.innerHTML = `<h4>What the labels say</h4><p class="meta" role="alert">The labels could not be read. Select the ingredient again to retry.</p>`;
  }
}

async function run() {
  const s = state(), mine = ++ticket;
  input.value = s.q;
  form.elements.type.value = s.type;
  document.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.example === s.q)));
  results.setAttribute("aria-busy", "true");
  skeleton();
  try {
    const data = await getJSON("api/search", { q: s.q, type: s.type });
    if (mine === ticket) draw(s, data);
  } catch {
    if (mine === ticket) failed(run);
  }
  results.setAttribute("aria-busy", "false");
}

async function provenance() {
  try {
    const { info: i, timings } = await getJSON("api/info", {});
    $("#provenance").textContent = `openFDA drug labels, export of ${i.export_date}, downloaded on ${i.downloaded_on}. ` +
      `Licence: ${i.licence}. Loaded ${nf.format(+i.rows_loaded)} of the ${nf.format(+i.labels_in_export)} labels in the export: ` +
      `the ones with an ingredient name and an indications text` + (+i.sample_fraction < 1 ? `, and of those a ${i.sample_fraction * 100}% sample.` : ".");
    $("#timings tbody").innerHTML = timings.map((t) => `<tr><td>${esc(t.step)}</td><td class="num">${esc(t.seconds)}</td><td class="num">${esc(t.rows)}</td></tr>`).join("");
  } catch {
    $("#provenance").textContent = "The database did not answer.";
  }
}

form.addEventListener("submit", (e) => { e.preventDefault(); go({ q: input.value.trim(), drug: "" }); run(); });
form.addEventListener("change", (e) => { if (e.target.name === "type") { go({ q: input.value.trim(), type: e.target.value, drug: "" }); run(); } });
input.addEventListener("focus", () => input.select());
// choosing a suggestion from the list starts the search, typing a letter does not
input.addEventListener("input", (e) => { if (e.inputType !== "insertText" && !e.inputType?.startsWith("delete") && input.value) form.requestSubmit(); });
document.addEventListener("click", (e) => {
  const ex = e.target.closest("[data-example]");
  if (ex) { go({ q: ex.dataset.example, drug: "" }); run(); if (!ex.classList.contains("chip")) results.scrollIntoView(); return; }
  const row = e.target.closest(".row-btn");
  if (row) open(row.dataset.drug);
});
addEventListener("popstate", run);
run();
provenance();
