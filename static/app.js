"use strict";
// SOC Investigation UI. All dynamic text goes through textContent (never
// innerHTML), so log content can't inject markup.

const S = { status: null, customer: null, customerId: "", investigations: [], inv: null, tab: "summary" };
const $ = (id) => document.getElementById(id);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "checked" || k === "disabled" || k === "selected") el[k] = !!v;
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function toast(msg, kind = "") {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast " + kind;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.add("hidden"), kind === "error" ? 7000 : 3000);
}

async function api(path, opts = {}) {
  const headers = { "X-Analyst": localStorage.getItem("analyst") || "" };
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.json);
  }
  const res = await fetch("/api" + path, { method: opts.method || "GET", headers, body: opts.body });
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty */ }
  if (!res.ok) {
    let msg = data && data.detail ? data.detail : res.statusText;
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join("; ");
    throw new Error(msg);
  }
  return data;
}

async function copy(text, label = "Copied") {
  try {
    await navigator.clipboard.writeText(text);
    toast(label);
  } catch (_) {
    const ta = h("textarea", { class: "offscreen" }, text);
    document.body.append(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    toast(label);
  }
}

function download(name, text) {
  const a = h("a", { href: URL.createObjectURL(new Blob([text], { type: "text/markdown" })), download: name });
  document.body.append(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}

const custPath = () => "/customers/" + encodeURIComponent(S.customerId);
const invPath = (id) => custPath() + "/investigations/" + encodeURIComponent(id);

// ------------------------------------------------------------------ boot
async function boot() {
  $("analystName").value = localStorage.getItem("analyst") || "";
  $("analystName").addEventListener("change", (e) => localStorage.setItem("analyst", e.target.value.trim()));
  $("customerSelect").addEventListener("change", (e) => selectCustomer(e.target.value));
  $("btnNew").addEventListener("click", showNewForm);
  $("btnConfig").addEventListener("click", () => showConfig());
  $("btnNewCustomer").addEventListener("click", showNewCustomer);
  $("btnCatalog").addEventListener("click", showCatalog);
  $("invSearch").addEventListener("input", renderInvList);
  $("invStatus").addEventListener("change", renderInvList);
  try {
    S.status = await api("/status");
  } catch (e) {
    $("main").replaceChildren(h("div", { class: "empty" }, "Cannot reach the API: " + e.message));
    return;
  }
  if (S.status.auth) $("analystName").parentElement.classList.add("hidden");
  for (const st of S.status.statuses) $("invStatus").append(h("option", { value: st }, st));
  await loadCustomers();
  const saved = localStorage.getItem("customer");
  if (saved && [...$("customerSelect").options].some((o) => o.value === saved)) {
    $("customerSelect").value = saved;
    await selectCustomer(saved);
  } else {
    showWelcome();
  }
}

async function loadCustomers() {
  const list = await api("/customers");
  const sel = $("customerSelect");
  sel.replaceChildren(h("option", { value: "" }, "Select customer…"));
  for (const c of list) sel.append(h("option", { value: c.id }, c.name + (c.error ? " (config error)" : "")));
}

function renderLLMBadge() {
  const b = $("llmBadge");
  const llm = (S.customer && S.customer.llm) || S.status.llm;
  if (!llm.configured) {
    b.className = "badge local";
    b.textContent = "Local analysis only";
    b.title = llm.reason || "";
  } else if (llm.available) {
    b.className = "badge " + (llm.external ? "external" : "local");
    b.textContent = (llm.external ? "External LLM available: " : "Local LLM: ") + llm.provider + " · " + llm.model;
    b.title = llm.external ? "Logs are only sent when you choose LLM analysis and confirm." : "";
  } else {
    b.className = "badge off";
    b.textContent = "LLM disabled for this customer";
    b.title = llm.reason;
  }
  const banner = $("banner");
  if (S.customer && S.customer.warnings && S.customer.warnings.length) {
    banner.className = "banner warn";
    banner.textContent = "Customer config warnings: " + S.customer.warnings.join(" · ");
  } else {
    banner.className = "banner hidden";
  }
}

function showWelcome() {
  S.customer = null; S.inv = null;
  renderLLMBadge();
  $("main").replaceChildren(h("div", { class: "empty" },
    h("h2", {}, "Select a customer to begin"),
    h("p", {}, "Each customer has its own schema, KQL conventions and ticket template. Investigations are stored per customer and never shared across customers.")));
}

async function selectCustomer(id) {
  S.customerId = id; S.customer = null; S.inv = null; S.investigations = [];
  $("invList").replaceChildren();
  $("btnNew").disabled = $("btnConfig").disabled = !id;
  if (!id) { localStorage.removeItem("customer"); return showWelcome(); }
  localStorage.setItem("customer", id);
  try {
    S.customer = await api(custPath());
  } catch (e) { toast(e.message, "error"); return; }
  renderLLMBadge();
  await refreshInvList();
  showCustomerHome();
}

async function refreshInvList() {
  S.investigations = await api(custPath() + "/investigations");
  renderInvList();
}

function renderInvList() {
  const q = $("invSearch").value.toLowerCase();
  const st = $("invStatus").value;
  const items = S.investigations.filter((i) => (!st || i.status === st) &&
    (!q || (i.id + " " + i.title + " " + i.event_type).toLowerCase().includes(q)));
  $("invList").replaceChildren(...items.map((i) => h("li", {
      class: "inv-item" + (S.inv && S.inv.id === i.id ? " active" : ""), onclick: () => openInvestigation(i.id),
    },
    h("div", { class: "inv-top" }, h("span", { class: "inv-id" }, i.id), statusPill(i.status)),
    h("div", { class: "inv-title" }, i.title),
    h("div", { class: "inv-meta" }, [i.event_type, i.severity, (i.updated || "").slice(0, 16).replace("T", " ")].filter(Boolean).join(" · ")))));
  if (!items.length) $("invList").append(h("li", { class: "muted pad" }, "No investigations yet."));
}

const statusPill = (s) => h("span", { class: "pill st-" + (s || "").toLowerCase().replace(/\s+/g, "-") }, s);

function showCustomerHome() {
  const c = S.customer;
  S.inv = null;
  renderInvList();
  $("main").replaceChildren(h("div", { class: "page" },
    h("h2", {}, c.name),
    h("div", { class: "grid2" },
      card("Environment", c.environment.length ? h("ul", {}, c.environment.map((e) => h("li", {}, e))) : h("p", { class: "muted" }, "Not documented.")),
      card("Settings", h("dl", { class: "kv" }, Object.entries(c.settings).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])))),
    card("Tables (" + c.tables.length + ")", h("table", { class: "tbl" },
      h("thead", {}, h("tr", {}, h("th", {}, "Table"), h("th", {}, "Product"), h("th", {}, "Time field"), h("th", {}, "Fields"), h("th", {}, "Defined in"))),
      h("tbody", {}, c.tables.map((t) => h("tr", {}, h("td", { class: "mono" }, t.name), h("td", {}, t.product),
        h("td", { class: "mono" }, t.roles.time || "—"), h("td", {}, String(t.fields.length)), h("td", { class: "muted" }, t.source)))))),
    c.investigation_notes ? card("Investigation notes", h("pre", { class: "md" }, c.investigation_notes)) : null,
    h("div", { class: "row" }, h("button", { class: "primary", onclick: showNewForm }, "+ New investigation"))));
}

function card(title, ...body) {
  return h("section", { class: "card" }, h("h3", {}, title), ...body);
}

// ------------------------------------------------------------------ new investigation
function llmChoice(prefix) {
  const llm = S.customer.llm;
  const wrap = h("div", { class: "llm-choice" });
  const rules = h("input", { type: "radio", name: prefix + "mode", value: "rules", checked: true });
  const withLLM = h("input", { type: "radio", name: prefix + "mode", value: "llm", disabled: !llm.available });
  const confirm = h("input", { type: "checkbox" });
  const warn = h("div", { class: "external-warn hidden" },
    h("strong", {}, "External processing. "),
    "The log (secrets redacted, truncated to the configured limit), the analyst context and " + S.customer.name +
    "'s customer profile will be sent to " + llm.provider + " (" + llm.model + "). ",
    h("label", { class: "inline" }, confirm, " I confirm this data may leave this system."));
  const sync = () => warn.classList.toggle("hidden", !(withLLM.checked && llm.external));
  rules.addEventListener("change", sync);
  withLLM.addEventListener("change", sync);
  wrap.append(
    h("label", { class: "inline" }, rules, " Local rules engine (no data leaves this system)"),
    h("label", { class: "inline" + (llm.available ? "" : " disabled") }, withLLM,
      llm.configured ? ` Rules + LLM (${llm.provider}${llm.external ? ", external" : ", local"})` : " Rules + LLM (not configured)"),
    llm.available ? null : h("div", { class: "muted small" }, llm.reason),
    warn);
  return { el: wrap, get: () => ({ use_llm: withLLM.checked, confirm_external: confirm.checked }) };
}

function showNewForm() {
  S.inv = null; renderInvList();
  const title = h("input", { placeholder: "Short title, e.g. Failed admin sign-in from TOR exit", maxlength: 300 });
  const log = h("textarea", { class: "mono log-input", placeholder: "Paste the raw log / alert / event JSON, CSV, syslog or key=value here", spellcheck: "false" });
  const file = h("input", { type: "file", accept: ".json,.csv,.log,.txt,.xml,.tsv,.ndjson,.jsonl" });
  const ctx = h("textarea", { class: "ctx-input", placeholder: "Optional context: what triggered this, ticket references, what the user said…" });
  const mode = llmChoice("new");
  const submit = h("button", { class: "primary" }, "Create & analyse");
  const lim = S.status.limits;
  submit.addEventListener("click", async () => {
    const m = mode.get();
    if (!log.value.trim() && !file.files.length) return toast("Paste a log or choose a file.", "error");
    if (file.files.length && file.files[0].size > lim.upload_bytes) return toast("File exceeds the upload limit.", "error");
    if (m.use_llm && S.customer.llm.external && !m.confirm_external) return toast("Confirm external processing or choose local analysis.", "error");
    const fd = new FormData();
    fd.append("title", title.value);
    fd.append("raw_log", log.value);
    fd.append("context", ctx.value);
    fd.append("use_llm", m.use_llm);
    fd.append("confirm_external", m.confirm_external);
    if (file.files.length) fd.append("file", file.files[0]);
    submit.disabled = true;
    submit.textContent = m.use_llm ? "Analysing with LLM… (can take a minute)" : "Analysing…";
    try {
      const inv = await api(custPath() + "/investigations", { method: "POST", body: fd });
      await refreshInvList();
      showInvestigation(inv);
      if (inv.analysis && inv.analysis.engine.error) toast(inv.analysis.engine.error, "error");
    } catch (e) {
      toast(e.message, "error");
      submit.disabled = false;
      submit.textContent = "Create & analyse";
    }
  });
  $("main").replaceChildren(h("div", { class: "page" },
    h("h2", {}, "New investigation · " + S.customer.name),
    card("Event", h("label", {}, "Title", title),
      h("label", {}, "Raw log", log),
      h("div", { class: "row" }, h("label", { class: "inline" }, "…or upload a file ", file),
        h("span", { class: "muted small" }, `max ${Math.round(lim.upload_bytes / 1024 / 1024)} MB, text only`)),
      h("label", {}, "Analyst context", ctx)),
    card("Analysis mode", mode.el),
    h("div", { class: "row" }, submit)));
}

// ------------------------------------------------------------------ workspace
async function openInvestigation(id) {
  try {
    showInvestigation(await api(invPath(id)));
  } catch (e) { toast(e.message, "error"); }
}

const TABS = [["summary", "Summary"], ["observables", "Observables"], ["hypotheses", "Hypotheses"], ["kql", "KQL"],
  ["findings", "Findings & notes"], ["ticket", "Ticket"], ["raw", "Raw log"], ["history", "History"]];

function showInvestigation(inv) {
  if (inv.customer_id !== S.customerId) return; // never render another customer's data
  S.inv = inv;
  renderInvList();
  const a = inv.analysis;
  const title = h("input", { class: "title-input", value: inv.title, maxlength: 300 });
  const status = h("select", {}, S.status.statuses.map((s) => h("option", { value: s, selected: s === inv.status }, s)));
  const sev = h("select", {}, h("option", { value: "" }, "Severity: not set"),
    S.status.severities.map((s) => h("option", { value: s, selected: s === inv.severity }, s)));
  const save = h("button", { onclick: () => patch({ title: title.value, status: status.value, severity: sev.value }, "Saved") }, "Save");
  const engine = a ? a.engine : null;
  const head = h("div", { class: "ws-head" },
    h("div", { class: "ws-id" }, h("span", { class: "mono" }, inv.id), " · ", S.customer.name, " · created ",
      inv.created.slice(0, 16).replace("T", " "), " by ", inv.created_by),
    h("div", { class: "row" }, title, status, sev, save),
    engine ? h("div", { class: "engine " + (engine.external ? "external" : "") },
      engine.mode === "rules+llm"
        ? `Analysis: local rules + ${engine.provider} (${engine.model})${engine.external ? " — data was sent to an external LLM" : ""}`
        : "Analysis: local rules engine (no data left this system)",
      engine.error ? h("span", { class: "err" }, " · " + engine.error) : null,
      " · ", (a.analyzed_at || "").replace("T", " ")) : null);
  const tabs = h("nav", { class: "tabs" }, TABS.map(([k, label]) => h("button", {
    class: "tab" + (S.tab === k ? " active" : ""), onclick: () => { S.tab = k; showInvestigation(S.inv); } },
    label + (k === "kql" && a ? ` (${a.kql_queries.length})` : "") + (k === "observables" && a ? ` (${a.observables.length})` : ""))));
  const body = h("div", { class: "tab-body" }, renderTab(S.tab, inv));
  $("main").replaceChildren(h("div", { class: "page ws" }, head, tabs, body));
}

async function patch(changes, msg) {
  try {
    const inv = await api(invPath(S.inv.id), { method: "PATCH", json: changes });
    S.inv = inv;
    await refreshInvList();
    showInvestigation(inv);
    if (msg) toast(msg);
  } catch (e) { toast(e.message, "error"); }
}

function list(items, empty = "None.") {
  return items && items.length ? h("ul", {}, items.map((i) => h("li", {}, i))) : h("p", { class: "muted" }, empty);
}

function renderTab(tab, inv) {
  const a = inv.analysis;
  if (!a && !["findings", "raw", "history", "ticket"].includes(tab)) {
    return h("div", {}, h("p", { class: "muted" }, "Not analysed yet."), reanalyseBox());
  }
  switch (tab) {
    case "summary": return h("div", {},
      card("Event", h("p", { class: "summary" }, a.summary),
        a.llm_event_type ? h("p", {}, h("span", { class: "tag llm" }, "LLM"), " event type: " + a.llm_event_type) : null,
        h("div", { class: "types" }, a.event_types.map((e) => h("div", { class: "etype" },
          h("span", { class: "conf c-" + e.confidence }, e.confidence), " ", h("strong", {}, e.label), " · ", e.product,
          h("div", { class: "muted small" }, e.evidence.join("; "))))),
        h("p", { class: "small" }, "Mapped tables: ", a.mapping.tables.length
          ? a.mapping.tables.map((m) => m.table + " (" + m.reasons.join("; ") + ")").join(" · ")
          : "none — check the customer schema")),
      h("div", { class: "grid3" },
        card("Observed", h("p", { class: "muted small" }, "Facts present in the log."), list(a.observed)),
        card("Inferred", h("p", { class: "muted small" }, "Reasoned conclusions; confirm before relying on them."), list(a.inferred)),
        card("Unknown", h("p", { class: "muted small" }, "Not determinable from the data."), list(a.unknown))),
      card("Recommended investigation", h("ol", {}, a.recommended_steps.map((s) => h("li", {}, s)))),
      reanalyseBox());
    case "observables": return card("Observables", a.observables.length ? h("table", { class: "tbl" },
      h("thead", {}, h("tr", {}, h("th", {}, "Type"), h("th", {}, "Value"), h("th", {}, "Tags"), h("th", {}, "Source"), h("th", {}))),
      h("tbody", {}, a.observables.map((o) => h("tr", {},
        h("td", {}, o.label), h("td", { class: "mono wrap" }, o.value),
        h("td", {}, o.tags.map((t) => h("span", { class: "tag " + t }, t))), h("td", { class: "muted small" }, o.sources.join(", ")),
        h("td", {}, h("button", { class: "small", onclick: () => copy(o.value) }, "Copy")))))) : h("p", { class: "muted" }, "No observables found."),
      a.observables.length ? h("button", { onclick: () => copy(a.observables.map((o) => o.type + "\t" + o.value).join("\n"), "All observables copied") }, "Copy all") : null);
    case "hypotheses": return card("Hypotheses", h("p", { class: "muted small" }, "Possibilities to test; none are confirmed."),
      h("ol", { class: "hyp" }, a.hypotheses.map((x) => h("li", {}, h("strong", {}, x.title), " ",
        h("span", { class: "tag " + x.source }, x.source === "llm" ? "LLM" : "rules"), h("div", { class: "muted" }, x.rationale)))));
    case "kql": return h("div", {}, a.kql_queries.length ? a.kql_queries.map(kqlCard) : h("p", { class: "muted" }, "No queries generated."), kqlScratch());
    case "findings": return findingsTab(inv);
    case "ticket": return ticketTab(inv);
    case "raw": return h("div", {},
      card("Analyst context", h("pre", { class: "mono raw" }, inv.context || "(none)")),
      card("Raw log" + (inv.source_name ? " · " + inv.source_name : "") + (a ? ` · ${a.parsed.format}, ${a.parsed.records} record(s)` : ""),
        h("pre", { class: "mono raw" }, inv.raw_log)));
    case "history": return card("History", h("table", { class: "tbl" }, h("tbody", {}, inv.history.slice().reverse().map((e) =>
      h("tr", {}, h("td", { class: "mono small" }, e.at.replace("T", " ")), h("td", {}, e.by), h("td", {}, e.action), h("td", { class: "muted" }, e.detail))))),
      inv.llm_used.length ? h("p", { class: "small" }, "LLM used: " + inv.llm_used.map((u) => `${u.at} ${u.provider}/${u.model}${u.external ? " (external)" : ""}`).join("; ")) : h("p", { class: "muted small" }, "No LLM has processed this investigation."));
  }
  return null;
}

function reanalyseBox() {
  const mode = llmChoice("re");
  const btn = h("button", {}, "Re-analyse");
  btn.addEventListener("click", async () => {
    const m = mode.get();
    if (m.use_llm && S.customer.llm.external && !m.confirm_external) return toast("Confirm external processing first.", "error");
    btn.disabled = true; btn.textContent = "Analysing…";
    try {
      const inv = await api(invPath(S.inv.id) + "/analyze", { method: "POST", json: m });
      showInvestigation(inv);
      toast(inv.analysis.engine.error || "Analysis updated", inv.analysis.engine.error ? "error" : "");
    } catch (e) { toast(e.message, "error"); btn.disabled = false; btn.textContent = "Re-analyse"; }
  });
  return h("details", { class: "card" }, h("summary", {}, "Re-analyse this investigation"), mode.el, h("div", { class: "row" }, btn));
}

function validationView(v) {
  const box = h("div", { class: "validation v-" + v.status },
    h("strong", {}, { ok: "✓ Schema check passed", warning: "⚠ Schema check: warnings", error: "✗ Schema check: errors" }[v.status]),
    v.errors.length ? h("ul", {}, v.errors.map((e) => h("li", { class: "err" }, e))) : null,
    v.warnings.length ? h("ul", {}, v.warnings.map((w) => h("li", {}, w))) : null,
    h("div", { class: "note" }, v.note));
  return box;
}

function kqlCard(q) {
  const ta = h("textarea", { class: "mono kql", spellcheck: "false", value: q.query });
  ta.rows = Math.min(24, q.query.split("\n").length + 1);
  let vbox = validationView(q.validation);
  const wrap = h("div", {});
  wrap.append(vbox);
  const revalidate = h("button", { class: "small" }, "Re-validate edited query");
  revalidate.addEventListener("click", async () => {
    try {
      const v = await api(custPath() + "/kql/validate", { method: "POST", json: { query: ta.value } });
      wrap.replaceChildren(validationView(v));
    } catch (e) { toast(e.message, "error"); }
  });
  return h("section", { class: "card kql-card" },
    h("div", { class: "kql-head" }, h("h3", {}, q.id + " · " + q.title),
      h("span", { class: "tag " + q.source }, q.source === "llm" ? "LLM-suggested" : "rule-based"),
      h("span", { class: "mono small" }, q.table)),
    h("dl", { class: "kv" }, h("dt", {}, "Purpose"), h("dd", {}, q.purpose),
      h("dt", {}, "Time range"), h("dd", {}, q.time_range || ""),
      h("dt", {}, "Why these fields"), h("dd", {}, q.rationale),
      h("dt", {}, "Expected result"), h("dd", {}, q.expected_result)),
    ta,
    h("div", { class: "row" }, h("button", { class: "primary small", onclick: () => copy(ta.value, "Query copied") }, "Copy KQL"), revalidate),
    wrap);
}

function kqlScratch() {
  const ta = h("textarea", { class: "mono kql", rows: 6, spellcheck: "false", placeholder: "Write or paste KQL to check it against " + S.customer.name + "'s schema" });
  const out = h("div", {});
  return card("KQL scratchpad", ta, h("div", { class: "row" },
    h("button", { onclick: async () => {
      try { out.replaceChildren(validationView(await api(custPath() + "/kql/validate", { method: "POST", json: { query: ta.value } }))); }
      catch (e) { toast(e.message, "error"); }
    } }, "Validate against schema"),
    h("button", { onclick: () => copy(ta.value) }, "Copy")), out);
}

function findingsTab(inv) {
  const findings = h("textarea", { class: "notes", value: inv.findings, placeholder: "What did your queries show? Confirmed facts, query results, conclusions…" });
  const notes = h("textarea", { class: "notes", value: inv.analyst_notes, placeholder: "Working notes, contacts, timeline, open questions…" });
  return h("div", {},
    card("Findings", h("p", { class: "muted small" }, "Goes into the ticket's findings section. Record only what you verified."), findings),
    card("Analyst notes", notes),
    h("div", { class: "row" }, h("button", { class: "primary", onclick: () => patch({ findings: findings.value, analyst_notes: notes.value }, "Notes saved") }, "Save findings & notes")));
}

function ticketTab(inv) {
  const ta = h("textarea", { class: "mono ticket", value: inv.ticket, placeholder: "Generate a ticket from " + S.customer.name + "'s template." });
  const missing = h("div", {});
  const gen = h("button", { class: "primary" }, inv.ticket ? "Regenerate from template" : "Generate ticket");
  gen.addEventListener("click", async () => {
    if (inv.ticket && !confirm("Regenerating replaces the current ticket text, including manual edits. Continue?")) return;
    try {
      const r = await api(invPath(inv.id) + "/ticket", { method: "POST" });
      ta.value = r.ticket;
      S.inv.ticket = r.ticket;
      missing.replaceChildren(r.missing.length
        ? h("div", { class: "validation v-warning" }, "Analyst input required: " + r.missing.join(", ") + ". Fill these in before sending.")
        : h("div", { class: "validation v-ok" }, "Template filled (" + r.template_source + " template)."));
    } catch (e) { toast(e.message, "error"); }
  });
  return h("div", {}, card("Ticket",
    h("p", { class: "muted small" }, "Filled only from this investigation's data. Missing values show as \"Unknown / Not observed\" or \"[Analyst input required]\". Secrets are redacted. Edit freely before copying."),
    h("div", { class: "row" }, gen,
      h("button", { onclick: () => patch({ ticket: ta.value }, "Ticket saved") }, "Save edits"),
      h("button", { onclick: () => copy(ta.value, "Ticket copied") }, "Copy"),
      h("button", { onclick: () => download(inv.id + ".md", ta.value) }, "Download .md")),
    missing, ta));
}

// ------------------------------------------------------------------ customer config
const FILE_LABELS = { customer: "customer.md", template: "templates/incident-ticket.md", schema: "schemas/", example: "examples/" };
const NEW_FILE_STUB = {
  schema: (c) => "# " + c.name + ": additional tables\n\n### TableName\nProduct: \nTime field: TimeGenerated\n- TimeGenerated\n- FieldName\n",
  example: () => "",
};

async function refreshCustomer() {
  S.customer = await api(custPath());
  renderLLMBadge();
  const sel = $("customerSelect");
  const opt = [...sel.options].find((o) => o.value === S.customerId);
  if (opt) opt.textContent = S.customer.name;
}

async function showConfig(selectKey = "customer") {
  S.inv = null; renderInvList();
  const c = S.customer;

  // -- customer details (rename)
  const nameInput = h("input", { value: c.name, maxlength: "200" });
  const rename = h("button", { class: "primary" }, "Save name");
  rename.addEventListener("click", async () => {
    try {
      await api(custPath(), { method: "PATCH", json: { name: nameInput.value } });
      await refreshCustomer();
      toast("Customer renamed to " + S.customer.name);
      showConfig(current);
    } catch (e) { toast(e.message, "error"); }
  });
  const details = card("Customer details",
    h("div", { class: "row" }, h("label", { class: "grow" }, "Display name", nameInput), rename),
    h("p", { class: "muted small" }, "Id: ", h("span", { class: "mono" }, c.id),
      " (folder customers/" + c.id + "/). The id does not change, so existing investigations stay linked."));

  // -- file editor
  const files = [["customer", "customer.md"], ["template", "templates/incident-ticket.md"]]
    .concat(c.schema_files.map((f) => ["schema:" + f, "schemas/" + f]))
    .concat((c.example_files || []).map((f) => ["example:" + f, "examples/" + f]));
  const editor = h("textarea", { class: "mono editor", spellcheck: "false" });
  const status = h("div", { class: "muted small" });
  const picker = h("select", {}, files.map(([k, l]) => h("option", { value: k }, l)));
  let current = "customer", loaded = "", isNew = false;
  const kindOf = (k) => { const i = k.indexOf(":"); return i < 0 ? [k, ""] : [k.slice(0, i), k.slice(i + 1)]; };
  const dirty = () => editor.value !== loaded;

  const del = h("button", {}, "Delete file");
  function updateButtons() {
    const [kind] = kindOf(current);
    del.classList.toggle("hidden", kind === "customer" || isNew);
    del.textContent = kind === "template" ? "Revert to default template" : "Delete file";
  }
  async function load(k) {
    current = k; isNew = false; picker.value = k;
    const [kind, filename] = kindOf(k);
    try {
      const r = await api(custPath() + "/files/" + kind + "?filename=" + encodeURIComponent(filename));
      editor.value = loaded = r.content;
      status.textContent = kind === "template" && r.source === "default"
        ? "Using the default template. Saving creates a customer-specific copy." : "";
      if (kind === "template" && r.source === "default") isNew = true;
    } catch (e) { toast(e.message, "error"); }
    updateButtons();
  }
  picker.addEventListener("change", () => {
    if (dirty() && !confirm("Discard unsaved changes to " + current + "?")) { picker.value = current; return; }
    load(picker.value);
  });

  const save = h("button", { class: "primary" }, "Save file");
  save.addEventListener("click", async () => {
    const [kind, filename] = kindOf(current);
    try {
      const r = await api(custPath() + "/files/" + kind, { method: "PUT", json: { content: editor.value, filename } });
      loaded = editor.value;
      await refreshCustomer();
      toast(`Saved ${FILE_LABELS[kind]}${filename}. ${r.tables} tables parsed.` + (r.warnings.length ? " Warnings: " + r.warnings.join("; ") : ""));
      if (isNew) showConfig(current);
    } catch (e) { toast(e.message, "error"); }
  });

  del.addEventListener("click", async () => {
    const [kind, filename] = kindOf(current);
    const label = FILE_LABELS[kind] + filename;
    if (!confirm(kind === "template" ? "Delete the customer template and use the default template?" : "Delete " + label + "? This cannot be undone.")) return;
    try {
      await api(custPath() + "/files/" + kind + "?filename=" + encodeURIComponent(filename), { method: "DELETE" });
      await refreshCustomer();
      toast("Deleted " + label);
      showConfig(kind === "template" ? "template" : "customer");
    } catch (e) { toast(e.message, "error"); }
  });

  // -- new file
  const newKind = h("select", {}, h("option", { value: "schema" }, "Schema file"), h("option", { value: "example" }, "Example log"));
  const newName = h("input", { placeholder: "defender-xdr.md", class: "small-input" });
  newKind.addEventListener("change", () => { newName.placeholder = newKind.value === "schema" ? "defender-xdr.md" : "failed-signin.json"; });
  const add = h("button", {}, "Add file");
  add.addEventListener("click", () => {
    const kind = newKind.value, name = newName.value.trim();
    const ok = kind === "schema" ? /^[A-Za-z0-9][A-Za-z0-9._-]*\.md$/.test(name)
      : /^[A-Za-z0-9][A-Za-z0-9._-]*\.(json|jsonl|csv|tsv|txt|log|xml|md)$/.test(name);
    if (!ok) return toast(kind === "schema" ? "Name must look like defender-xdr.md" : "Name must look like failed-signin.json (.json .jsonl .csv .tsv .txt .log .xml .md)", "error");
    if (dirty() && !confirm("Discard unsaved changes to " + current + "?")) return;
    const key = kind + ":" + name;
    if (![...picker.options].some((o) => o.value === key)) picker.append(h("option", { value: key }, FILE_LABELS[kind] + name));
    picker.value = current = key; isNew = true;
    editor.value = NEW_FILE_STUB[kind](c); loaded = "";
    status.textContent = "New file. Click Save file to create it.";
    newName.value = "";
    updateButtons();
  });

  $("main").replaceChildren(h("div", { class: "page" },
    h("h2", {}, "Customer configuration · " + c.name),
    configTabs("files"),
    details,
    card("Files",
      h("p", { class: "muted small" }, "Tables are read from `###` headings under any `##` section whose title contains \"Table\" or \"Schema\" in customer.md, and from every file in schemas/. Mark field roles with e.g. `- AccountUpn (user)`. Example logs are reference samples only. Changes apply to new analyses."),
      h("div", { class: "row" }, picker, save, del, h("span", { class: "spacer" }), newKind, newName, add),
      status, editor)));
  await load(files.some(([k]) => k === selectKey) ? selectKey : "customer");
}

// ------------------------------------------------------------------ schema catalog
const safeLink = (url, text) => (/^https:\/\//.test(url || "")
  ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, text || url) : h("span", {}, text || ""));

function configTabs(active) {
  const t = (k, label, fn) => h("button", { class: "tab" + (active === k ? " active" : ""), onclick: fn }, label);
  return h("nav", { class: "tabs" },
    t("files", "Details & files", () => showConfig()),
    t("schema", "Schema selection", () => showSchemaSelection()));
}

function columnsView(schemaId, table) {
  const box = h("div", { class: "cols muted small" }, "Loading columns…");
  api(`/catalog/tables/${encodeURIComponent(schemaId)}/${encodeURIComponent(table)}`).then((t) => {
    box.replaceChildren(
      h("div", { class: "row" }, "Time field: ", h("span", { class: "mono" }, t.time_field || "none (snapshot table)"),
        " · ", safeLink(t.source, "Microsoft Learn page")),
      h("table", { class: "tbl" }, h("thead", {}, h("tr", {}, h("th", {}, "Column"), h("th", {}, "Type"), h("th", {}, "Description"))),
        h("tbody", {}, t.columns.map((c) => h("tr", {}, h("td", { class: "mono" }, c.name), h("td", {}, c.type), h("td", {}, c.description))))));
  }).catch((e) => { box.textContent = e.message; });
  return box;
}

async function showSchemaSelection() {
  S.inv = null; renderInvList();
  const c = S.customer;
  let cat, cur;
  try {
    [cat, cur] = await Promise.all([api("/catalog"), api(custPath() + "/catalog-selection")]);
  } catch (e) { return toast(e.message, "error"); }
  const page = h("div", { class: "page" }, h("h2", {}, "Customer configuration · " + c.name), configTabs("schema"));
  $("main").replaceChildren(page);
  if (!cat.schemas.length) {
    page.append(card("No schema catalog yet",
      h("p", {}, "Build the catalog first: open Schema catalog and click Pull from Microsoft."),
      h("button", { class: "primary", onclick: showCatalog }, "Open Schema catalog")));
    return;
  }

  // state: "schemaId|Table" -> checked
  const sel = new Set();
  for (const [sid, tables] of Object.entries(cur.selection)) for (const t of tables) sel.add(sid + "|" + t);
  const initial = [...sel].sort().join(",");
  let scope = cur.scope;

  const counter = h("strong", {});
  const dupWarn = h("div", { class: "warn-text small" });
  const filter = h("input", { placeholder: "Filter tables (name or description)…", class: "grow-input" });
  const onlySel = h("input", { type: "checkbox" });
  const apply = h("button", { class: "primary" }, "Apply to " + c.name);
  const sections = [];
  const catNames = new Set();

  function refreshCounts() {
    counter.textContent = `${sel.size} tables selected`;
    const byName = {};
    for (const k of sel) { const [sid, t] = k.split("|"); (byName[t] = byName[t] || []).push(sid); }
    const dups = Object.entries(byName).filter(([, v]) => v.length > 1).map(([t]) => t);
    dupWarn.textContent = dups.length ? `Selected in more than one schema (columns will be merged, first time field wins): ${dups.slice(0, 8).join(", ")}${dups.length > 8 ? "…" : ""}` : "";
    const dirty = [...sel].sort().join(",") !== initial || scope !== cur.scope;
    apply.textContent = (dirty ? "Apply to " : "Applied · re-apply to ") + c.name;
    for (const s of sections) s.update();
  }

  for (const schema of cat.schemas) {
    const all = h("input", { type: "checkbox" });
    const count = h("span", { class: "muted small" });
    const list = h("div", { class: "tlist" });
    const groups = new Map();  // category -> { rows, box, ... }; tables arrive sorted by category
    const rows = schema.tables.map((t) => {
      const key = schema.id + "|" + t.name;
      const cb = h("input", { type: "checkbox", checked: sel.has(key) });
      cb.addEventListener("change", () => { cb.checked ? sel.add(key) : sel.delete(key); refreshCounts(); });
      const more = h("button", { class: "small ghost" }, "columns");
      let open = null;
      const row = h("div", { class: "trow" },
        h("label", { class: "inline tname" }, cb, h("span", { class: "mono" }, t.name)),
        h("span", { class: "muted small tcount" }, t.field_count + " fields" + (t.time_field ? "" : " · no time field")),
        h("span", { class: "muted small tdesc" }, t.description), more);
      const wrap = h("div", {}, row);
      more.addEventListener("click", () => {
        if (open) { open.remove(); open = null; return; }
        open = columnsView(schema.id, t.name); wrap.append(open);
      });
      const catName = t.category || "Other";
      if (!groups.has(catName)) {
        const gAll = h("input", { type: "checkbox" });
        const gCount = h("span", { class: "muted small" });
        const gList = h("div", {});
        const box = h("details", { class: "cat" },
          h("summary", {}, h("label", { class: "inline", onclick: (e) => e.stopPropagation() }, gAll),
            h("strong", {}, catName), " ", gCount),
          gList);
        const g = { name: catName, rows: [], box, gAll, gCount, gList };
        gAll.addEventListener("change", () => {
          for (const r of g.rows) if (!r.wrap.classList.contains("hidden")) {
            r.cb.checked = gAll.checked; gAll.checked ? sel.add(r.key) : sel.delete(r.key);
          }
          refreshCounts();
        });
        groups.set(catName, g);
        list.append(box);
        catNames.add(catName);
      }
      const r = { t, key, cb, wrap, cat: catName };
      const g = groups.get(catName);
      g.rows.push(r); g.gList.append(wrap);
      return r;
    });
    for (const g of groups.values()) if (g.rows.some((r) => sel.has(r.key))) g.box.open = true;
    const visible = () => rows.filter((r) => !r.wrap.classList.contains("hidden"));
    const tri = (box, vis) => {
      const vn = vis.filter((r) => sel.has(r.key)).length;
      box.checked = vis.length > 0 && vn === vis.length;
      box.indeterminate = vn > 0 && vn < vis.length;
    };
    all.addEventListener("change", () => {
      for (const r of visible()) { r.cb.checked = all.checked; all.checked ? sel.add(r.key) : sel.delete(r.key); }
      refreshCounts();
    });
    const det = h("details", { class: "card schema" },
      h("summary", {}, h("label", { class: "inline", onclick: (e) => e.stopPropagation() }, all),
        h("strong", {}, schema.name), " ", count, " ", h("span", { class: "tag" }, schema.origin),
        " ", h("span", { class: "muted small" }, groups.size + " categories"),
        " ", safeLink(schema.source, "source")),
      list);
    if (rows.some((r) => sel.has(r.key))) det.open = true;
    sections.push({
      det, rows,
      update() {
        const n = rows.filter((r) => sel.has(r.key)).length;
        count.textContent = `${n} of ${rows.length} selected`;
        tri(all, visible());
        for (const g of groups.values()) {
          const gn = g.rows.filter((r) => sel.has(r.key)).length;
          g.gCount.textContent = `${gn} of ${g.rows.length}`;
          tri(g.gAll, g.rows.filter((r) => !r.wrap.classList.contains("hidden")));
        }
      },
      filter(q, only, catF) {
        let shown = 0;
        for (const g of groups.values()) {
          let gShown = 0;
          for (const r of g.rows) {
            const hit = (!q || r.t.name.toLowerCase().includes(q) || (r.t.description || "").toLowerCase().includes(q))
              && (!only || sel.has(r.key)) && (!catF || r.cat === catF);
            r.wrap.classList.toggle("hidden", !hit); if (hit) gShown++;
          }
          g.box.classList.toggle("hidden", gShown === 0);
          if ((q || only || catF) && gShown) g.box.open = true;
          shown += gShown;
        }
        det.classList.toggle("hidden", shown === 0);
        if ((q || only || catF) && shown) det.open = true;
      },
    });
  }
  const catPick = h("select", {}, h("option", { value: "" }, "All categories"),
    ...[...catNames].map((n) => h("option", { value: n }, n)));
  const runFilter = () => {
    const q = filter.value.trim().toLowerCase();
    for (const s of sections) s.filter(q, onlySel.checked, catPick.value);
    refreshCounts();
  };
  filter.addEventListener("input", runFilter);
  onlySel.addEventListener("change", runFilter);
  catPick.addEventListener("change", runFilter);

  const scopeSel = h("input", { type: "radio", name: "scope", checked: scope === "selected" });
  const scopeAll = h("input", { type: "radio", name: "scope", checked: scope === "all" });
  scopeSel.addEventListener("change", () => { scope = "selected"; refreshCounts(); });
  scopeAll.addEventListener("change", () => { scope = "all"; refreshCounts(); });

  apply.addEventListener("click", async () => {
    const selection = {};
    for (const k of sel) { const [sid, t] = k.split("|"); (selection[sid] = selection[sid] || []).push(t); }
    try {
      const r = await api(custPath() + "/catalog-selection", { method: "PUT", json: { selection, scope } });
      await refreshCustomer();
      toast(`Applied: ${r.selected_tables} tables written to ${r.written.join(", ") || "no files"}. ` +
        (r.scope === "selected" ? `Analysis now uses only these ${r.table_count} tables.` : `Scope: all tables (${r.table_count}).`));
      showSchemaSelection();
    } catch (e) { toast(e.message, "error"); }
  });

  page.append(
    card("How this works",
      h("p", { class: "small" }, "Tick the schemas and tables this customer actually has, then Apply. Each selected schema is saved as ",
        h("span", { class: "mono" }, "schemas/catalog-<schema>.md"),
        " in the customer's folder, with every column from the catalog. With the first option, analysis, KQL generation and validation use only the selected tables. Tables in customer.md or other schema files that are not selected are ignored; their role hints and notes still apply to selected tables with the same name."),
      h("p", { class: "muted small" }, cat.generated || "", " · In use now: ", h("strong", {}, String(cur.table_count)),
        " tables, scope ", h("strong", {}, cur.scope)),
      cur.ignored_tables.length ? h("p", { class: "warn-text small" }, "Ignored (defined in customer files but not selected): " + cur.ignored_tables.join(", ")) : null,
      h("label", { class: "inline" }, scopeSel, " Use only the selected tables (recommended)"),
      h("label", { class: "inline" }, scopeAll, " Use all tables defined in the customer files (selection is still saved)")),
    h("div", { class: "row sticky-bar" }, filter, catPick, h("label", { class: "inline" }, onlySel, " selected only"),
      h("span", { class: "spacer" }), counter, apply),
    dupWarn,
    ...sections.map((s) => s.det));
  refreshCounts();
}

async function showCatalog() {
  S.inv = null; renderInvList();
  let cat;
  try { cat = await api("/catalog"); } catch (e) { return toast(e.message, "error"); }
  const page = h("div", { class: "page" }, h("h2", {}, "Schema catalog"));
  $("main").replaceChildren(page);

  // -- status & refresh
  const prog = h("progress", { max: "1", value: "0", class: "hidden" });
  const msg = h("div", { class: "muted small" });
  const pull = h("button", { class: "primary", disabled: !cat.fetch_enabled }, "Pull from Microsoft");
  let timer = null;
  async function poll() {
    try {
      const j = await api("/catalog/refresh");
      prog.classList.toggle("hidden", !j.running);
      if (j.total) { prog.max = j.total; prog.value = j.done; }
      msg.textContent = j.running ? `Fetching ${j.done}/${j.total || "?"} · ${j.message}` :
        j.error ? "Last pull failed: " + j.error :
        j.result ? `Last pull ${j.finished_at}: ${j.result.tables} tables (${j.result.fetched} pages fetched, ${j.result.errors.length} errors${j.result.errors.length ? ": " + j.result.errors.slice(0, 3).join("; ") : ""}).` : "";
      pull.disabled = j.running || !cat.fetch_enabled;
      if (j.running) { timer = setTimeout(poll, 1500); }
      else if (timer) { timer = null; toast(j.error ? "Catalog pull failed" : "Catalog updated"); showCatalog(); }
    } catch (e) { msg.textContent = e.message; }
  }
  pull.addEventListener("click", async () => {
    try { await api("/catalog/refresh", { method: "POST" }); timer = 1; poll(); } catch (e) { toast(e.message, "error"); }
  });
  page.append(card("Source",
    h("p", { class: "small" }, "Tables and columns are pulled from the official Microsoft Learn reference pages: ",
      safeLink("https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables-category", "Azure Monitor / Sentinel tables (Security category)"),
      " and ", safeLink("https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-schema-tables", "Defender XDR advanced hunting tables"),
      ". Only public documentation pages are requested; no customer data is sent. Saved to catalog/schema-catalog.md."),
    h("p", { class: "muted small" }, cat.exists ? (cat.generated || "Catalog present.") : "No catalog yet.",
      cat.fetch_enabled ? "" : " Pulling is disabled (CATALOG_FETCH_ENABLED=false)."),
    h("table", { class: "tbl" }, h("tbody", {}, cat.schemas.map((s) => h("tr", {},
      h("td", {}, h("strong", {}, s.name)), h("td", {}, h("span", { class: "tag" }, s.origin)),
      h("td", {}, s.tables.length + " tables"), h("td", {}, s.tables.reduce((a, t) => a + t.field_count, 0) + " columns"),
      h("td", { class: "mono small" }, "time: " + (s.time_field || "-")))))),
    h("div", { class: "row" }, pull, prog), msg));
  poll();

  // -- browse
  const q = h("input", { placeholder: "Search tables or categories, e.g. signin, DeviceProcess, Email & collaboration…", class: "grow-input" });
  const results = h("div", {});
  const all = cat.schemas.flatMap((s) => s.tables.map((t) => ({ s, t })));
  function search() {
    const term = q.value.trim().toLowerCase();
    const hits = term ? all.filter(({ t }) => t.name.toLowerCase().includes(term) || (t.description || "").toLowerCase().includes(term)
      || (t.category || "").toLowerCase().includes(term)) : [];
    results.replaceChildren(...hits.slice(0, 60).map(({ s, t }) => {
      const wrap = h("div", {});
      const btn = h("button", { class: "small ghost" }, "columns");
      let open = null;
      btn.addEventListener("click", () => { if (open) { open.remove(); open = null; } else { open = columnsView(s.id, t.name); wrap.append(open); } });
      wrap.append(h("div", { class: "trow" }, h("span", { class: "mono tname" }, t.name),
        h("span", { class: "muted small tcount" }, s.name + " · " + (t.category || "Other") + " · " + t.field_count + " fields"),
        h("span", { class: "muted small tdesc" }, t.description), btn));
      return wrap;
    }), term && hits.length > 60 ? h("p", { class: "muted small" }, `${hits.length - 60} more; refine the search.`) : "");
  }
  q.addEventListener("input", search);
  page.append(card("Browse", q, results));

  // -- custom tables
  const ed = h("textarea", { class: "mono editor small-editor", spellcheck: "false" });
  api("/catalog/custom").then((r) => { ed.value = r.content; }).catch((e) => toast(e.message, "error"));
  const save = h("button", { class: "primary" }, "Save custom schemas");
  save.addEventListener("click", async () => {
    try {
      const r = await api("/catalog/custom", { method: "PUT", json: { content: ed.value } });
      toast(`Saved ${r.schemas} custom schema(s), ${r.tables} tables.`); showCatalog();
    } catch (e) { toast(e.message, "error"); }
  });
  page.append(card("Custom schemas and tables",
    h("p", { class: "muted small" }, "For custom logs (_CL), third-party connectors or anything not on Microsoft Learn. Use one `## Schema: Name` section per group with `Origin: custom`, then `### TableName` blocks with a `| Column | Type | Description |` table. These sections are kept when you pull from Microsoft, and can be selected per customer like any other table."),
    h("div", { class: "row" }, save), ed));
}

function showNewCustomer() {
  const name = h("input", { placeholder: "Customer display name" });
  const id = h("input", { placeholder: "id (optional, e.g. northwind)", pattern: "[a-z0-9-]+" });
  const btn = h("button", { class: "primary" }, "Create customer");
  btn.addEventListener("click", async () => {
    try {
      const c = await api("/customers", { method: "POST", json: { name: name.value, id: id.value.trim() || null } });
      await loadCustomers();
      $("customerSelect").value = c.id;
      await selectCustomer(c.id);
      showConfig();
      toast("Customer created from _template. Edit customer.md to describe their tables.");
    } catch (e) { toast(e.message, "error"); }
  });
  $("main").replaceChildren(h("div", { class: "page" }, h("h2", {}, "New customer"),
    card("Details", h("label", {}, "Name", name), h("label", {}, "Id", id),
      h("p", { class: "muted small" }, "Creates customers/<id>/ from customers/_template."), h("div", { class: "row" }, btn))));
}

boot();
