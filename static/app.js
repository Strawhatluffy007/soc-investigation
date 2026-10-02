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
    else if (k === "style") el.style.cssText = v;  // CSSOM is allowed by the CSP; style="" attributes are not
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
  t.onclick = () => t.classList.add("hidden");
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
  $("btnTemplate").addEventListener("click", () => showTemplateEditor());
  $("btnNewCustomer").addEventListener("click", showNewCustomer);
  $("btnCatalog").addEventListener("click", showCatalog);
  $("btnLLM").addEventListener("click", () => showLLMSettings());
  $("invSearch").addEventListener("input", renderInvList);
  $("invStatus").addEventListener("change", renderInvList);
  $("extToggle").addEventListener("change", toggleExternal);
  $("btnTheme").addEventListener("click", toggleTheme);
  $("btnMenu").addEventListener("click", () => document.body.classList.toggle("side-open"));
  $("scrim").addEventListener("click", closeSidebar);
  for (const b of document.querySelectorAll(".side-nav .nav-item, #btnNew"))
    b.addEventListener("click", () => { setNav(b.id); closeSidebar(); });
  document.addEventListener("keydown", shortcuts);
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

// ------------------------------------------------------------------ theme, sidebar, shortcuts
function toggleTheme() {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("theme", next); } catch (_) { /* storage blocked */ }
}

function closeSidebar() { document.body.classList.remove("side-open"); }

function setNav(id) {
  for (const b of document.querySelectorAll(".side-nav .nav-item")) b.classList.toggle("active", b.id === id);
}

function shortcuts(e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const tag = (e.target.tagName || "").toLowerCase();
  if (["input", "textarea", "select"].includes(tag) || e.target.isContentEditable) {
    if (e.key === "Escape") e.target.blur();
    return;
  }
  if (e.key === "/") { e.preventDefault(); document.body.classList.add("side-open"); $("invSearch").focus(); }
  else if (e.key === "n" && !$("btnNew").disabled) { e.preventDefault(); setNav(""); showNewForm(); }
  else if (e.key === "t") toggleTheme();
  else if (e.key === "Escape") closeSidebar();
}

const hue = (s) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";
const SEV_COLOR = { Critical: "var(--err)", High: "var(--ext)", Medium: "var(--warn)", Low: "var(--info)", Informational: "var(--faint)" };

async function loadCustomers() {
  const list = await api("/customers");
  S.customers = list;
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
    b.textContent = llm.blocked_by === "env" ? "External LLM disabled (server config)"
      : llm.blocked_by === "switch" ? "External LLM off · local analysis only"
      : llm.blocked_by === "customer" ? "External LLM blocked for " + S.customer.name : "LLM not ready";
    b.title = llm.reason;
  }
  const sw = $("extSwitch"), t = $("extToggle");
  const anyExternal = (llm.choices || []).some((c) => c.external && c.blocked_by !== "config");
  sw.classList.toggle("hidden", !((llm.configured && llm.external) || anyExternal));
  t.checked = llm.allow_external;
  t.disabled = !llm.env_allow_external;
  sw.classList.toggle("disabled", t.disabled);
  sw.title = t.disabled ? "Locked off: LLM_ALLOW_EXTERNAL=false in the server .env"
    : "Turn sending data to the external LLM on or off for everyone (audited)";
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
  setNav("");
  const custs = S.customers || [];
  const pick = (id) => { $("customerSelect").value = id; selectCustomer(id); };
  $("main").replaceChildren(h("div", { class: "page" },
    h("section", { class: "hero" },
      h("div", { class: "eyebrow" }, "Security operations"),
      h("h2", {}, "Welcome back" + (localStorage.getItem("analyst") ? ", " + localStorage.getItem("analyst") : "")),
      h("p", {}, "Paste or upload a log, get the event explained, the observables extracted, KQL to hunt with and a ticket ready to send. Everything stays per customer and local unless you choose an external LLM.")),
    h("div", { class: "section-title" }, h("h3", {}, "Choose a customer (" + custs.length + ")"),
      h("button", { class: "small", onclick: () => { setNav("btnNewCustomer"); showNewCustomer(); } }, "+ Add customer")),
    custs.length ? h("div", { class: "cust-grid" }, custs.map((c, i) => h("button", {
        class: "cust-card", style: "animation-delay:" + i * 40 + "ms", onclick: () => pick(c.id) },
      h("div", { class: "cc-head" },
        h("span", { class: "avatar", style: "--h:" + hue(c.id) }, initials(c.name)),
        h("div", {}, h("div", { class: "cc-name" }, c.name), h("div", { class: "cc-id" }, c.id))),
      h("div", { class: "cc-meta" },
        c.error ? h("span", { class: "tag", style: "--c:var(--err)" }, "config error") : h("span", { class: "tag rules" }, (c.table_count || 0) + " tables"),
        h("span", { class: "tag " + (c.allow_external_llm ? "external" : "internal") }, c.allow_external_llm ? "external LLM allowed" : "local only")))))
      : h("p", { class: "muted" }, "No customers yet. Add one, or copy the samples: cp -r samples/customers/*/ customers/"),
    h("div", { class: "section-title" }, h("h3", {}, "How it works")),
    h("div", { class: "steps" },
      [["Pick a customer", "Each has its own schema, KQL rules and ticket template. Data never crosses customers."],
       ["Add a log", "Paste or upload JSON, CSV, CEF or plain text. Secrets are redacted before analysis."],
       ["Investigate", "Review the summary, observables, hypotheses and validated KQL. Optionally ask an LLM."],
       ["Ticket it", "Generate a ticket from the customer's template, edit it and copy it out."]]
        .map(([b, p], i) => h("div", { class: "step" }, h("span", { class: "num" }, String(i + 1)), h("b", {}, b), h("p", {}, p))))));
}

async function selectCustomer(id) {
  S.customerId = id; S.customer = null; S.inv = null; S.investigations = [];
  $("invList").replaceChildren(); $("invCount").textContent = "";
  $("btnNew").disabled = $("btnConfig").disabled = $("btnTemplate").disabled = !id;
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
      class: "inv-item" + (S.inv && S.inv.id === i.id ? " active" : ""), tabindex: "0",
      style: "--sev:" + (SEV_COLOR[i.severity] || "transparent"),
      onclick: () => { setNav(""); closeSidebar(); openInvestigation(i.id); },
      onkeydown: (e) => { if (e.key === "Enter") { setNav(""); closeSidebar(); openInvestigation(i.id); } },
    },
    h("div", { class: "inv-top" }, h("span", { class: "inv-id" }, i.id), statusPill(i.status)),
    h("div", { class: "inv-title" }, i.title),
    h("div", { class: "inv-meta" }, [i.event_type, i.severity, (i.updated || "").slice(0, 16).replace("T", " ")].filter(Boolean).join(" · ")))));
  $("invCount").textContent = S.investigations.length ? String(S.investigations.length) : "";
  if (!items.length) $("invList").append(h("li", { class: "muted pad small" },
    S.investigations.length ? "No investigations match the filter." : "No investigations yet. Press N to start one."));
}

const statusPill = (s) => h("span", { class: "pill st-" + (s || "").toLowerCase().replace(/\s+/g, "-") }, s);

function showCustomerHome() {
  const c = S.customer;
  S.inv = null;
  renderInvList();
  setNav("");
  const invs = S.investigations || [];
  const open = invs.filter((i) => !["Resolved", "Closed"].includes(i.status));
  const hot = invs.filter((i) => ["Critical", "High"].includes(i.severity) && !["Resolved", "Closed"].includes(i.status));
  const recent = [...invs].sort((a, b) => (b.updated || "").localeCompare(a.updated || "")).slice(0, 6);
  const stat = (v, l, color) => h("div", { class: "stat", style: "--c:" + color }, h("div", { class: "v" }, String(v)), h("div", { class: "l" }, l));
  $("main").replaceChildren(h("div", { class: "page" },
    h("div", { class: "page-head" },
      h("span", { class: "avatar", style: "--h:" + hue(c.id) }, initials(c.name)),
      h("div", {}, h("h2", {}, c.name), h("div", { class: "muted small mono" }, c.id)),
      h("div", { class: "spacer" }),
      h("button", { onclick: () => { setNav("btnConfig"); showConfig(); } }, "Configure"),
      h("button", { class: "primary", onclick: showNewForm }, "+ New investigation")),
    h("div", { class: "stats" },
      stat(open.length, "Open investigations", "var(--accent)"),
      stat(hot.length, "Open high / critical", hot.length ? "var(--err)" : "var(--ok)"),
      stat(invs.length, "Total investigations", "var(--info)"),
      stat(c.tables.length, "Tables in schema", "var(--accent-2)")),
    recent.length ? card("Recent investigations", h("ul", { class: "recent" }, recent.map((i) => h("li", { onclick: () => openInvestigation(i.id) },
      h("span", { class: "inv-id" }, i.id), h("span", { class: "t" }, i.title), i.severity ? h("span", { class: "tag", style: "--c:" + (SEV_COLOR[i.severity] || "var(--muted)") }, i.severity) : null,
      statusPill(i.status))))) : null,
    h("div", { class: "grid2" },
      card("Environment", c.environment.length ? h("ul", {}, c.environment.map((e) => h("li", {}, e))) : h("p", { class: "muted" }, "Not documented.")),
      card("Settings", h("dl", { class: "kv" }, Object.entries(c.settings).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])))),
    card("Tables (" + c.tables.length + ")", h("table", { class: "tbl" },
      h("thead", {}, h("tr", {}, h("th", {}, "Table"), h("th", {}, "Product"), h("th", {}, "Time field"), h("th", {}, "Fields"), h("th", {}, "Defined in"))),
      h("tbody", {}, c.tables.map((t) => h("tr", {}, h("td", { class: "mono" }, t.name), h("td", {}, t.product),
        h("td", { class: "mono" }, t.roles.time || "—"), h("td", {}, String(t.fields.length)), h("td", { class: "muted" }, t.source)))))),
    c.investigation_notes ? card("Investigation notes", h("pre", { class: "md" }, c.investigation_notes)) : null,
    null));
}

function card(title, ...body) {
  return h("section", { class: "card" }, h("h3", {}, title), ...body);
}

// ------------------------------------------------------------------ new investigation
function llmChoice(prefix) {
  const llm = S.customer.llm;
  const choices = llm.choices || [];
  let saved = "";
  try { saved = localStorage.getItem("llmPick") || ""; } catch (e) { /* storage blocked */ }
  const pickable = choices.filter((c) => c.available);
  const start = (pickable.find((c) => c.id === saved) || pickable.find((c) => c.default) || pickable[0] || {}).id || "";
  const pick = h("select", { class: "llm-pick" }, choices.map((c) => h("option",
    { value: c.id, disabled: !c.available, selected: c.id === start, title: c.reason || "" },
    `${c.label}${c.default ? " (default)" : ""} · ${c.external ? "external" : "local"}${c.available ? "" : " · " + shortReason(c)}`)));
  const cur = () => choices.find((c) => c.id === pick.value) || {};

  const wrap = h("div", { class: "llm-choice" });
  const rules = h("input", { type: "radio", name: prefix + "mode", value: "rules", checked: true });
  const withLLM = h("input", { type: "radio", name: prefix + "mode", value: "llm", disabled: !pickable.length });
  const confirm = h("input", { type: "checkbox" });
  const dest = h("span");
  const warn = h("div", { class: "external-warn hidden" },
    h("strong", {}, "External processing. "),
    "The log (secrets redacted, truncated to the configured limit), the analyst context and " + S.customer.name +
    "'s customer profile will be sent to ", dest, ". ",
    h("label", { class: "inline" }, confirm, " I confirm this data may leave this system."));
  const sync = () => {
    const c = cur();
    dest.textContent = `${c.label || "the LLM"} (${c.model || ""})`;
    warn.classList.toggle("hidden", !(withLLM.checked && c.external));
    pick.disabled = !withLLM.checked;
  };
  pick.addEventListener("change", () => {
    confirm.checked = false;  // confirmation is per destination
    try { localStorage.setItem("llmPick", pick.value); } catch (e) { /* storage blocked */ }
    sync();
  });
  rules.addEventListener("change", sync);
  withLLM.addEventListener("change", sync);
  const blocked = llm.blocked_by === "customer" || choices.some((c) => c.blocked_by === "customer");
  wrap.append(...[
    h("label", { class: "inline" }, rules, " Local rules engine (no data leaves this system)"),
    h("div", { class: "row" },
      h("label", { class: "inline" + (pickable.length ? "" : " disabled") }, withLLM, " Rules + LLM:"),
      pick,
      h("button", { class: "small ghost", onclick: () => showLLMSettings() }, "LLM settings")),
    pickable.length ? null : h("div", { class: "muted small" }, llm.reason || "No LLM is ready. Set one up in LLM settings."),
    blocked ? allowCustomerButton() : null,
    warn].filter(Boolean));
  sync();
  return { el: wrap, get: () => ({ use_llm: withLLM.checked, confirm_external: confirm.checked,
    llm_provider: withLLM.checked ? pick.value : "", external: withLLM.checked && !!cur().external }) };
}

function shortReason(c) {
  return { config: "not set up", env: "blocked by server", switch: "external off", customer: "blocked for customer" }[c.blocked_by] || "unavailable";
}

function allowCustomerButton() {
  const b = h("button", { class: "small" }, "Allow external LLM for " + S.customer.name);
  b.addEventListener("click", async () => {
    if (!confirm(`Allow ${S.customer.name}'s logs to be sent to external LLMs when you choose LLM analysis and confirm?\n\nThis sets allow_external_llm: true in ${S.customer.name}'s customer.md (audited).`)) return;
    try {
      S.customer = await api(custPath() + "/external-llm", { method: "PUT", json: { enabled: true } });
      renderLLMBadge();
      toast("External LLM allowed for " + S.customer.name);
      if (S.inv) showInvestigation(S.inv); else showNewForm();
    } catch (e) { toast(e.message, "error"); }
  });
  return h("div", { class: "row" }, b);
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
    if (m.use_llm && m.external && !m.confirm_external) return toast("Confirm external processing or choose local analysis.", "error");
    const fd = new FormData();
    fd.append("title", title.value);
    fd.append("raw_log", log.value);
    fd.append("context", ctx.value);
    fd.append("use_llm", m.use_llm);
    fd.append("confirm_external", m.confirm_external);
    fd.append("llm_provider", m.llm_provider);
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

const TABS = [["summary", "Summary"], ["followup", "Follow-up"], ["observables", "Observables"], ["hypotheses", "Hypotheses"], ["kql", "KQL"],
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
    label + (k === "followup" && (inv.followups || []).length ? ` (${inv.followups.length})` : "")
      + (k === "kql" && a ? ` (${a.kql_queries.length})` : "") + (k === "observables" && a ? ` (${a.observables.length})` : ""))));
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
  if (!a && !["findings", "raw", "history", "ticket", "followup"].includes(tab)) {
    return h("div", {}, h("p", { class: "muted" }, "Not analysed yet."), reanalyseBox());
  }
  switch (tab) {
    case "summary": return h("div", {},
      a.analyst_response ? h("section", { class: "card answer" }, h("h3", {}, h("span", { class: "tag llm" }, "LLM"),
        " Response to your latest input"), h("div", { class: "answer-text" }, a.analyst_response)) : null,
      h("div", { class: "continue-cta" },
        h("div", {}, h("strong", {}, "Continue the investigation"),
          h("div", { class: "muted small" }, "Add more Defender / Sentinel / raw logs, ask a question, or ask for a ticket.")),
        h("button", { class: "primary", onclick: () => { S.tab = "followup"; showInvestigation(S.inv); } }, "Add input")),
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
    case "followup": return followupTab(inv);
    case "findings": return findingsTab(inv);
    case "ticket": return ticketTab(inv);
    case "raw": return h("div", {},
      card("Analyst context", h("pre", { class: "mono raw" }, inv.context || "(none)")),
      card("Raw log" + (inv.source_name ? " · " + inv.source_name : "") + (a ? ` · ${a.parsed.format}, ${a.parsed.records} record(s)` : ""),
        h("pre", { class: "mono raw" }, inv.raw_log)),
      (inv.followups || []).filter((f) => f.kind === "log").map((f) => card(`Additional log ${f.id}`
        + (f.source_name ? " · " + f.source_name : "") + " · " + fuWhen(f), h("pre", { class: "mono raw" }, f.text))));
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
    if (m.use_llm && m.external && !m.confirm_external) return toast("Confirm external processing first.", "error");
    btn.disabled = true; btn.textContent = "Analysing…";
    try {
      const inv = await api(invPath(S.inv.id) + "/analyze", { method: "POST",
        json: { use_llm: m.use_llm, confirm_external: m.confirm_external, llm_provider: m.llm_provider } });
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

// ------------------------------------------------------------------ follow-up input
const FU_PROMPTS = ["Create a ticket for this incident", "Is this a true positive or benign? Explain why.",
  "What should I check next, and with which queries?", "Write a short summary I can send to the customer."];

function fuWhen(f) { return f.at.slice(0, 16).replace("T", " ") + " by " + f.by; }

function followupTab(inv) {
  const fus = inv.followups || [];
  const timeline = fus.length
    ? h("ol", { class: "fu-list" }, fus.slice().reverse().map((f) => h("li", { class: "fu-item fu-" + f.kind },
      h("div", { class: "fu-meta" },
        h("span", { class: "tag " + (f.kind === "log" ? "fu-log" : "fu-note") }, f.kind === "log" ? "Log" : "Input"),
        h("span", { class: "mono small" }, f.id), f.source_name ? h("span", { class: "small" }, f.source_name) : null,
        h("span", { class: "muted small" }, fuWhen(f)),
        f.kind === "log" ? h("span", { class: "muted small" }, f.chars.toLocaleString() + " chars") : null),
      h(f.kind === "log" ? "pre" : "div", { class: f.kind === "log" ? "mono raw fu-log-text" : "fu-note-text" }, f.text),
      fuOutput(f))))
    : h("p", { class: "muted" }, "Nothing added yet. Input you add here is kept with the investigation and used in every re-analysis.");
  return h("div", {}, followupComposer(inv), card("Follow-up timeline", timeline));
}

function fuOutput(f) {
  const o = f.output;
  if (!o) return null;
  const eng = o.engine || {};
  const parts = [];
  if (o.reanalyzed) {
    parts.push(h("div", { class: "fu-out-meta muted small" },
      eng.mode === "rules+llm" ? `Re-analysed with local rules + ${eng.provider} (${eng.model})${eng.external ? ", external" : ""}`
        : "Re-analysed with the local rules engine", " · ", o.at.slice(0, 16).replace("T", " ")));
    if (eng.error) parts.push(h("div", { class: "validation v-warning" }, eng.error));
    if (o.answer) parts.push(h("div", { class: "fu-answer" }, h("span", { class: "tag llm" }, "LLM"), " ", o.answer));
    else if (f.kind === "note" && eng.mode !== "rules+llm") {
      parts.push(h("p", { class: "muted small" }, "Questions are answered only when you re-analyse with an LLM. The input is kept and used in later analyses."));
    }
    if (o.summary) parts.push(h("p", { class: "small" }, h("strong", {}, "Summary: "), o.summary));
    if (o.new_event_types && o.new_event_types.length) parts.push(h("p", { class: "small" }, h("strong", {}, "New event types: "), o.new_event_types.join(", ")));
    if (o.new_observables && o.new_observables.length) {
      parts.push(h("div", { class: "small" }, h("strong", {}, `New observables (${o.new_observables.length}): `),
        o.new_observables.map((x) => h("span", { class: "fu-obs", title: x.type }, h("span", { class: "muted" }, x.type + " "), h("span", { class: "mono" }, x.value)))));
    }
    if (o.new_queries && o.new_queries.length) {
      parts.push(h("div", { class: "small" }, h("strong", {}, "New / updated KQL: "), o.new_queries.map((q) =>
        h("button", { class: "chip", type: "button", onclick: () => { S.tab = "kql"; showInvestigation(S.inv); } }, q.id + " · " + q.title))));
    }
    if (!o.answer && !(o.new_observables || []).length && !(o.new_queries || []).length && !(o.new_event_types || []).length && !eng.error) {
      parts.push(h("p", { class: "muted small" }, "No new observables, event types or queries from this input."));
    }
  } else {
    parts.push(h("div", { class: "fu-out-meta muted small" }, "Added without re-analysis"));
  }
  if (o.ticket && o.ticket.generated) {
    parts.push(h("div", { class: "row small" }, h("span", { class: "tag fu-ticket" }, "Ticket"),
      " Generated." + (o.ticket.missing.length ? " Analyst input required: " + o.ticket.missing.join(", ") + "." : "")
        + ((o.ticket.drafted || []).length ? " LLM-drafted (review): " + o.ticket.drafted.join(", ") + "." : ""),
      h("button", { class: "small", onclick: () => { S.tab = "ticket"; showInvestigation(S.inv); } }, "Open ticket")));
  }
  return h("div", { class: "fu-output" }, h("div", { class: "fu-out-head" }, "Output"), parts);
}

function followupComposer(inv) {
  const lim = S.status.limits;
  let kind = "log";
  const text = h("textarea", { class: "mono log-input fu-text", spellcheck: "false" });
  const file = h("input", { type: "file", accept: ".json,.csv,.log,.txt,.xml,.tsv,.ndjson,.jsonl" });
  const fileRow = h("div", { class: "row" }, h("label", { class: "inline" }, "…or upload a file ", file),
    h("span", { class: "muted small" }, `max ${Math.round(lim.upload_bytes / 1024 / 1024)} MB, text only`));
  const chips = h("div", { class: "chips" }, FU_PROMPTS.map((p) => h("button", { class: "chip", type: "button",
    onclick: () => { text.value = text.value.trim() ? text.value.trim() + "\n" + p : p; text.focus(); syncTicket(); } }, p)));
  const seg = h("div", { class: "seg", role: "radiogroup" });
  const setKind = (k) => {
    kind = k;
    [...seg.children].forEach((b) => b.classList.toggle("active", b.dataset.k === k));
    text.classList.toggle("mono", k === "log");
    text.placeholder = k === "log"
      ? "Paste more logs: Defender alert / evidence JSON, advanced hunting results, Sentinel rows, raw syslog…"
      : "Ask a question or give direction, e.g. \"user confirmed they were travelling\", \"create a ticket for this incident\"…";
    fileRow.classList.toggle("hidden", k !== "log");
    chips.classList.toggle("hidden", k !== "note");
    syncTicket();
  };
  seg.append(
    h("button", { type: "button", "data-k": "log", onclick: () => setKind("log") }, "More logs (Defender / raw)"),
    h("button", { type: "button", "data-k": "note", onclick: () => setKind("note") }, "Question / general input"));
  const reanalyze = h("input", { type: "checkbox", checked: true });
  const ticket = h("input", { type: "checkbox" });
  const ticketHint = h("span", { class: "muted small" });
  const syncTicket = () => {
    const asks = kind === "note" && /\b(create|generate|make|raise|open|draft|write|prepare)\b[^.\n]{0,40}\bticket\b/i.test(text.value);
    ticketHint.textContent = asks && !ticket.checked ? " (your input asks for a ticket, so one will be generated)" : "";
  };
  text.addEventListener("input", syncTicket);
  ticket.addEventListener("change", syncTicket);
  const mode = llmChoice("fu");
  const modeWrap = h("div", { class: "fu-mode" }, mode.el);
  reanalyze.addEventListener("change", () => modeWrap.classList.toggle("hidden", !reanalyze.checked));
  const submit = h("button", { class: "primary" }, "Add input");
  submit.addEventListener("click", async () => {
    const m = mode.get();
    if (!text.value.trim() && !(kind === "log" && file.files.length)) return toast("Type something or choose a file.", "error");
    if (kind === "log" && file.files.length && file.files[0].size > lim.upload_bytes) return toast("File exceeds the upload limit.", "error");
    if (reanalyze.checked && m.use_llm && m.external && !m.confirm_external) return toast("Confirm external processing or choose local analysis.", "error");
    const wantsTicket = ticket.checked || ticketHint.textContent;
    if (wantsTicket && inv.ticket && !confirm("This regenerates the ticket and replaces its current text, including manual edits. Continue?")) return;
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("text", text.value);
    fd.append("reanalyze", reanalyze.checked);
    fd.append("generate_ticket", ticket.checked);
    fd.append("use_llm", reanalyze.checked && m.use_llm);
    fd.append("confirm_external", m.confirm_external);
    fd.append("llm_provider", m.llm_provider);
    if (kind === "log" && file.files.length) fd.append("file", file.files[0]);
    submit.disabled = true;
    submit.textContent = reanalyze.checked ? (m.use_llm ? "Re-analysing with LLM… (can take a minute)" : "Re-analysing…") : "Adding…";
    try {
      const r = await api(invPath(inv.id) + "/followups", { method: "POST", body: fd });
      await refreshInvList();
      const err = r.inv.analysis && r.inv.analysis.engine.error;
      S.tab = "followup";
      showInvestigation(r.inv);
      if (err) toast(err, "error");
      else if (r.ticket) toast(r.ticket.missing.length ? "Ticket generated. Analyst input required: " + r.ticket.missing.join(", ") : "Ticket generated");
      else toast(reanalyze.checked ? "Input added and analysis updated" : "Input added");
    } catch (e) {
      toast(e.message, "error");
      submit.disabled = false;
      submit.textContent = "Add input";
    }
  });
  setKind("log");
  return h("section", { class: "card fu-card" }, h("h3", {}, "Add to this investigation"),
    h("p", { class: "muted small" }, "Logs are parsed on their own and merged with the original (observables, queries). " +
      "Questions and input go to the LLM as analyst direction; its answer appears on the Summary tab. A closed or resolved investigation is reopened."),
    seg, text, fileRow, chips,
    h("div", { class: "row fu-opts" },
      h("label", { class: "inline" }, reanalyze, " Re-analyse with everything so far"),
      h("label", { class: "inline" }, ticket, " Generate / update the ticket", ticketHint)),
    modeWrap, h("div", { class: "row" }, submit));
}

function findingsTab(inv) {
  const ta = (value, placeholder, cls = "notes") => h("textarea", { class: cls, value: value || "", placeholder });
  const findings = ta(inv.findings, "What did your queries show? Confirmed facts, query results, conclusions… (the outcome)");
  const risk = ta(inv.risk, "Why this ticket is raised and what the risk is. Leave empty to use the event type and inferred risk.", "notes short");
  const soc = ta(inv.soc_actions, "What the SOC did, e.g. isolated device, disabled account, blocked IP, reset sessions…", "notes short");
  const client = ta(inv.client_actions, "What the client needs to do next, e.g. confirm activity with the user, reset password, reimage device…", "notes short");
  const notes = ta(inv.analyst_notes, "Working notes, contacts, timeline, open questions…");
  const a = inv.analysis || {};
  const d = (a.engine || {}).mode === "rules+llm" ? a.ticket_draft || {} : {};
  // Shows the LLM's draft under a field; the ticket uses it only while the field is empty.
  const draft = (box, text) => {
    if (!text) return null;
    return h("div", { class: "llm-draft" },
      h("div", { class: "row small" }, h("span", { class: "tag" }, "LLM draft"),
        h("span", { class: "muted" }, "Used in the ticket while the box is empty."),
        h("button", { class: "small", onclick: () => { box.value = text; box.focus(); } }, "Copy into box to edit")),
      h("div", { class: "draft-text small" }, text));
  };
  const clientDraft = (d.client_actions || []).map((x) => "- " + x).join("\n");
  return h("div", {},
    d.description ? card("Description (LLM draft)", h("p", { class: "muted small" }, "{{description}} in the ticket. Regenerated on each LLM analysis."),
      h("div", { class: "draft-text" }, d.description)) : null,
    card("Findings / outcome", h("p", { class: "muted small" }, "Goes into the ticket's findings / outcome. Record only what you verified."), findings, draft(findings, d.outcome)),
    h("div", { class: "grid3" },
      card("Why / risk", h("p", { class: "muted small" }, "{{why}} in the ticket."), risk, draft(risk, d.why)),
      card("Action taken by SOC", h("p", { class: "muted small" }, "{{soc_actions}}: your text, then what the record shows was done."), soc),
      card("Action for client", h("p", { class: "muted small" }, "{{client_actions}}: required in the SOC standard template."), client, draft(client, clientDraft))),
    card("Analyst notes", notes),
    h("div", { class: "row" }, h("button", { class: "primary", onclick: () => patch({ findings: findings.value, analyst_notes: notes.value,
      risk: risk.value, soc_actions: soc.value, client_actions: client.value }, "Saved") }, "Save findings, actions & notes")));
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
      missing.replaceChildren(...[r.missing.length
        ? h("div", { class: "validation v-warning" }, "Analyst input required: " + r.missing.join(", ") + ". Fill these in before sending.")
        : h("div", { class: "validation v-ok" }, "Template filled (" + r.template_source + " template)."),
        r.drafted.length ? h("div", { class: "validation v-warning" }, "LLM-drafted, review before sending: " + r.drafted.join(", ")
          + ". Write your own on the Findings & notes tab to replace them.") : null].filter(Boolean));
    } catch (e) { toast(e.message, "error"); }
  });
  return h("div", {}, card("Ticket",
    h("p", { class: "muted small" }, "Filled only from this investigation's data. Missing values show as \"Unknown / Not observed\" or \"[Analyst input required]\". Secrets are redacted. Edit freely before copying."),
    h("div", { class: "row" }, gen,
      h("button", { onclick: () => patch({ ticket: ta.value }, "Ticket saved") }, "Save edits"),
      h("button", { onclick: () => copy(ta.value, "Ticket copied") }, "Copy"),
      h("button", { onclick: () => download(inv.id + ".md", ta.value) }, "Download .md"),
      h("button", { class: "ghost", onclick: () => showTemplateEditor(inv.id) }, "Edit template")),
    missing, ta));
}

// ------------------------------------------------------------------ ticket template editor
async function showTemplateEditor(fromInv = "") {
  if (!S.customerId) return;
  setNav("btnTemplate"); closeSidebar();
  S.inv = null; renderInvList();
  let file, placeholders, invs, starters;
  try {
    [file, placeholders, invs, starters] = await Promise.all([api(custPath() + "/files/template"), api("/ticket-placeholders"),
      api(custPath() + "/investigations"), api("/ticket-templates")]);
  } catch (e) { return toast(e.message, "error"); }
  let loaded = file.content, source = file.source;
  const editor = h("textarea", { class: "mono editor tpl-editor", spellcheck: "false", value: loaded });
  const dirty = () => editor.value !== loaded;
  const srcBadge = h("span", { class: "tag" });
  const syncSource = () => {
    srcBadge.textContent = source === "default" ? "default template (shared)" : S.customer.name + " template";
    srcBadge.className = "tag " + (source === "default" ? "rules" : "internal");
    revert.classList.toggle("hidden", source === "default");
    dirtyMark.classList.toggle("hidden", !dirty());
  };
  const dirtyMark = h("span", { class: "tag external hidden" }, "unsaved");

  // insert {{placeholder}} at the cursor
  const insert = (name) => {
    const tok = "{{" + name + "}}", a = editor.selectionStart, b = editor.selectionEnd;
    editor.setRangeText(tok, a, b, "end");
    editor.focus(); changed();
  };
  const usedSet = new Set();
  const chips = placeholders.map((p) => h("button", { class: "chip ph-chip" + (p.required ? " req" : ""), type: "button",
    title: p.description + (p.required ? " (analyst must fill in)" : ""), "data-ph": p.name, onclick: () => insert(p.name) }, "{{" + p.name + "}}"));
  const phList = h("div", { class: "ph-list" }, placeholders.map((p, i) => h("div", { class: "ph-row" }, chips[i],
    h("span", { class: "muted small" }, p.description))));

  const pickInv = h("select", {}, h("option", { value: "" }, "Empty investigation"),
    invs.map((i) => h("option", { value: i.id, selected: i.id === (fromInv || (invs[0] || {}).id) }, i.id + " · " + i.title)));
  const preview = h("pre", { class: "mono raw tpl-preview" });
  const notes = h("div", {});
  let timer = null;
  async function renderPreview() {
    try {
      const r = await api(custPath() + "/ticket-template/preview", { method: "POST",
        json: { template: editor.value, investigation_id: pickInv.value } });
      preview.textContent = r.ticket;
      usedSet.clear(); r.used.forEach((u) => usedSet.add(u));
      chips.forEach((c) => c.classList.toggle("used", usedSet.has(c.dataset.ph)));
      notes.replaceChildren(...[
        r.unknown.length ? h("div", { class: "validation v-error" }, "Unknown placeholders (will show as \"Analyst input required\"): "
          + r.unknown.map((u) => "{{" + u + "}}").join(", ")) : null,
        r.missing.length ? h("div", { class: "validation v-warning" }, "Needs analyst input for this investigation: " + r.missing.join(", ")) : null,
        (r.drafted || []).length ? h("div", { class: "validation v-warning" }, "Filled from the LLM draft (review): " + r.drafted.join(", ")) : null,
        !r.unknown.length ? h("div", { class: "validation v-ok" }, `${r.used.length} placeholders, all valid.`) : null].filter(Boolean));
    } catch (e) { notes.replaceChildren(h("div", { class: "validation v-error" }, e.message)); }
  }
  function changed() {
    syncSource();
    clearTimeout(timer); timer = setTimeout(renderPreview, 350);
  }
  editor.addEventListener("input", changed);
  pickInv.addEventListener("change", renderPreview);

  const save = h("button", { class: "primary" }, "Save template");
  save.addEventListener("click", async () => {
    try {
      await api(custPath() + "/files/template", { method: "PUT", json: { content: editor.value, filename: "" } });
      loaded = editor.value; source = "customer";
      await refreshCustomer(); syncSource();
      toast("Template saved for " + S.customer.name + ". New and regenerated tickets use it.");
    } catch (e) { toast(e.message, "error"); }
  });
  const reset = h("button", { onclick: () => { if (!dirty() || confirm("Discard unsaved changes?")) { editor.value = loaded; changed(); } } }, "Discard changes");
  const revert = h("button", { class: "ghost" }, "Revert to default");
  revert.addEventListener("click", async () => {
    if (!confirm("Delete " + S.customer.name + "'s template and use the default template?")) return;
    try {
      await api(custPath() + "/files/template", { method: "DELETE" });
      await refreshCustomer();
      toast("Using the default template");
      showTemplateEditor(fromInv);
    } catch (e) { toast(e.message, "error"); }
  });
  const starterPick = h("select", {}, h("option", { value: "" }, "Load starter…"),
    starters.map((t) => h("option", { value: t.id }, t.label)));
  starterPick.addEventListener("change", () => {
    const t = starters.find((x) => x.id === starterPick.value);
    starterPick.value = "";
    if (!t || (editor.value.trim() && !confirm(`Replace the editor content with "${t.label}"? Nothing is saved until you click Save template.`))) return;
    editor.value = t.content; changed();
    toast("Loaded " + t.label + ". Review the preview, then Save template.");
  });
  const back = fromInv ? h("button", { onclick: () => { if (dirty() && !confirm("Leave without saving?")) return; S.tab = "ticket"; setNav(""); openInvestigation(fromInv); } }, "← Back to " + fromInv) : null;

  $("main").replaceChildren(h("div", { class: "page" },
    h("div", { class: "page-head" }, h("div", {}, h("h2", {}, "Ticket template · " + S.customer.name),
      h("div", { class: "row" }, srcBadge, dirtyMark,
        h("span", { class: "muted small" }, source === "default" ? "Saving creates a copy for " + S.customer.name + " only." : "customers/" + S.customer.id + "/templates/incident-ticket.md"))),
      h("div", { class: "row" }, back, starterPick, reset, revert, save)),
    h("div", { class: "tpl-grid" },
      h("div", {}, card("Template (Markdown)",
        h("p", { class: "muted small" }, "Write Markdown and use {{placeholders}}; click one on the right to insert it at the cursor. " +
          "Values come only from the investigation. Empty ones become \"Unknown / Not observed\"; severity and findings ask for analyst input. Secrets are always redacted."),
        editor),
        card("Preview", h("div", { class: "row" }, h("label", { class: "inline" }, "Preview with ", pickInv)), notes, preview)),
      card("Placeholders", phList))));
  syncSource();
  renderPreview();
}

// ------------------------------------------------------------------ customer config
const FILE_LABELS = { customer: "customer.md", template: "templates/incident-ticket.md", schema: "schemas/", example: "examples/" };
const NEW_FILE_STUB = {
  schema: (c) => "# " + c.name + ": additional tables\n\n### TableName\nProduct: \nTime field: TimeGenerated\n- TimeGenerated\n- FieldName\n",
  example: () => "",
};

async function toggleExternal() {
  const t = $("extToggle"), on = t.checked;
  if (!on || confirm("Turn ON external LLM use? Customer logs can then be sent to " +
      S.status.llm.provider + " when an analyst chooses LLM analysis and confirms.")) {
    try {
      S.status.llm = await api("/settings/external-llm", { method: "PUT", json: { enabled: on } });
      if (S.customerId) await refreshCustomer();
      toast("External LLM " + (on ? "enabled" : "disabled") + ".");
    } catch (e) { toast(e.message, "error"); }
  }
  renderLLMBadge();
  if (S.customerId && !S.inv && $("main").querySelector(".log-input")) showNewForm();
}

async function refreshCustomer() {
  S.customer = await api(custPath());
  renderLLMBadge();
  const sel = $("customerSelect");
  const opt = [...sel.options].find((o) => o.value === S.customerId);
  if (opt) opt.textContent = S.customer.name;
}

function extLLMRow(c) {
  const box = h("input", { type: "checkbox" });
  box.checked = c.allow_external_llm;
  const g = c.llm || {};
  box.addEventListener("change", async () => {
    try {
      S.customer = await api(custPath() + "/external-llm", { method: "PUT", json: { enabled: box.checked } });
      renderLLMBadge();
      toast(`External LLM ${box.checked ? "allowed" : "blocked"} for ${S.customer.name}.`);
    } catch (e) { box.checked = !box.checked; toast(e.message, "error"); }
  });
  const note = !g.env_allow_external ? "Server config (LLM_ALLOW_EXTERNAL=false) blocks external LLM for all customers."
    : !g.external_switch ? "The global External LLM switch in the header is off, so this has no effect until it is on."
    : "Saved as allow_external_llm under ## Settings in customer.md.";
  return h("div", {}, h("label", { class: "inline" }, box, "Allow external LLM for this customer"),
    h("p", { class: "muted small" }, note));
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
      " (folder customers/" + c.id + "/). The id does not change, so existing investigations stay linked."),
    extLLMRow(c));

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

// ------------------------------------------------------------------ LLM settings
const AUTH_GROUPS = [
  ["login", "Sign in with a subscription (no API key)",
    "Uses the plan you already pay for. The CLI runs on the Pi and is reached through the LLM bridge."],
  ["api_key", "API key (pay per use)", "Keys entered here are stored on the Pi in data/secrets (mode 0600), never shown again and never put in tickets or logs. A key set in .env takes priority."],
  ["local", "Local model", "Nothing leaves your network if the endpoint is local."],
  ["none", "Off", ""],
];

async function afterLLMChange(llm) {
  S.status.llm = llm;
  if (S.customerId) await refreshCustomer(); else renderLLMBadge();
}

async function showLLMSettings() {
  S.inv = null; renderInvList();
  let data, login = null;
  try { data = await api("/llm/providers"); } catch (e) { toast(e.message, "error"); return; }
  S.status.llm = data.llm;
  renderLLMBadge();
  const llm = data.llm;
  const page = h("div", { class: "page" }, h("h2", {}, "LLM settings"));

  const ext = llm.env_allow_external
    ? (llm.external_switch ? "External LLM use is ON (switch in the top bar)." : "External LLM use is OFF (switch in the top bar), so only local analysis runs.")
    : "External LLM use is locked off by LLM_ALLOW_EXTERNAL=false in .env.";
  page.append(card("Active provider",
    h("p", {}, h("strong", {}, (data.providers.find((p) => p.id === data.active) || {}).label || data.active),
      llm.available ? h("span", { class: "tag internal" }, "ready") : h("span", { class: "tag external" }, "not ready")),
    llm.available ? null : h("p", { class: "warn-text small" }, llm.reason),
    h("p", { class: "muted small" }, ext + " Customers can still opt out in Customer config. Logs are only sent when an analyst picks Rules + LLM and confirms.")));

  const loginBox = h("div", { class: "muted small" }, "Checking sign-in status…");
  for (const [auth, title, note] of AUTH_GROUPS) {
    const rows = data.providers.filter((p) => p.auth === auth);
    const c = card(title, note ? h("p", { class: "muted small" }, note) : null);
    if (auth === "login") c.append(loginBox);
    for (const p of rows) c.append(providerRow(p, data.active));
    page.append(c);
  }
  $("main").replaceChildren(page);

  try {
    login = await api("/llm/login-status");
    loginBox.textContent = "";
    for (const [cli, label] of [["claude", "Claude Code CLI"], ["codex", "Codex CLI (ChatGPT)"]]) {
      const st = login[cli] || {};
      loginBox.append(h("div", {}, label + ": ",
        !st.installed ? h("span", { class: "warn-text" }, "not installed")
          : st.logged_in ? h("span", { class: "tag internal" }, "signed in" + (st.method ? " · " + st.method : ""))
          : h("span", { class: "tag external" }, "not signed in")));
    }
  } catch (e) { loginBox.textContent = e.message; loginBox.className = "warn-text small"; }
}

function providerRow(p, active) {
  const row = h("div", { class: "prov" + (p.id === active ? " active" : "") });
  const use = h("button", { class: p.id === active ? "primary" : "" }, p.id === active ? "In use" : "Use this");
  use.disabled = p.id === active;
  use.addEventListener("click", async () => {
    if (p.external && !confirm(`Switch the LLM to ${p.label}? Customer logs will be sent to ${p.vendor} when an analyst chooses LLM analysis and confirms.`)) return;
    try {
      await afterLLMChange(await api("/llm/active", { method: "PUT", json: { provider: p.id } }));
      toast("LLM provider: " + p.label);
      showLLMSettings();
    } catch (e) { toast(e.message, "error"); }
  });
  const head = h("div", { class: "prov-head" },
    h("strong", {}, p.label), p.vendor ? h("span", { class: "muted small" }, p.vendor) : null,
    p.auth !== "none" ? h("span", { class: "tag " + (p.external ? "external" : "internal") }, p.external ? "external" : "local") : null,
    h("div", { class: "spacer" }), use);
  row.append(head);
  if (p.auth === "none") return row;

  const fields = h("div", { class: "row" });
  const model = h("input", { value: p.model, placeholder: p.default_model || "default", maxlength: "120", class: "grow-input" });
  const base = p.base_url_editable ? h("input", { value: p.effective_base_url, placeholder: p.base_url, class: "grow-input" }) : null;
  const saveOpts = h("button", {}, "Save");
  saveOpts.addEventListener("click", async () => {
    const json = { model: model.value };
    if (base) json.base_url = base.value;
    try {
      await afterLLMChange(await api("/llm/providers/" + p.id, { method: "PUT", json }));
      toast(p.label + " settings saved");
    } catch (e) { toast(e.message, "error"); }
  });
  fields.append(h("label", { class: "grow" }, "Model" + (p.models_hint ? " (" + p.models_hint + ")" : ""), model));
  if (base) fields.append(h("label", { class: "grow" }, "Endpoint URL", base));
  fields.append(saveOpts);
  row.append(fields);

  const actions = h("div", { class: "row" });
  const result = h("span", { class: "small" });
  if (p.auth === "api_key") {
    const src = p.key_source === "env" ? `Key set by ${p.key_env} in .env`
      : p.key_source === "saved" ? "Key saved" : "No key yet";
    actions.append(h("span", { class: "tag " + (p.key_source ? "internal" : "external") }, src));
    if (p.key_source !== "env") {
      const key = h("input", { type: "password", placeholder: p.key_source ? "Replace key" : "Paste API key", autocomplete: "off", class: "grow-input" });
      const saveKey = h("button", {}, "Save key");
      saveKey.addEventListener("click", async () => {
        try {
          const r = await api("/llm/providers/" + p.id + "/key", { method: "PUT", json: { api_key: key.value } });
          key.value = "";
          await afterLLMChange(r.llm);
          toast(p.label + " key saved");
          showLLMSettings();
        } catch (e) { toast(e.message, "error"); }
      });
      actions.append(key, saveKey);
      if (p.key_source === "saved") {
        const del = h("button", {}, "Remove key");
        del.addEventListener("click", async () => {
          if (!confirm("Remove the saved " + p.label + " key?")) return;
          try {
            const r = await api("/llm/providers/" + p.id + "/key", { method: "DELETE" });
            await afterLLMChange(r.llm);
            showLLMSettings();
          } catch (e) { toast(e.message, "error"); }
        });
        actions.append(del);
      }
    }
    if (p.docs) actions.append(safeLink(p.docs, "Get a key"));
  }
  if (p.auth === "login") {
    actions.append(h("span", { class: "muted small" }, "Sign in on the Pi: "), h("code", { class: "mono" }, p.login_cmd));
    if (p.cli === "codex") {
      const signIn = h("button", {}, "Sign in from browser");
      signIn.addEventListener("click", () => deviceLogin(p, result));
      actions.append(signIn);
    }
  }
  const test = h("button", {}, "Test");
  test.title = "Checks the key or sign-in. Sends no customer data and no prompt.";
  test.addEventListener("click", async () => {
    result.className = "small muted"; result.textContent = "Testing…";
    try {
      const r = await api("/llm/providers/" + p.id + "/test", { method: "POST" });
      result.className = "small"; result.style.color = "var(--ok)"; result.textContent = r.message;
    } catch (e) { result.className = "small err"; result.style.color = ""; result.textContent = e.message; }
  });
  actions.append(test, result);
  row.append(actions);
  return row;
}

async function deviceLogin(p, out) {
  out.className = "small muted"; out.textContent = "Starting sign-in…";
  try {
    let st = await api("/llm/providers/" + p.id + "/login", { method: "POST" });
    if (!st.code) {
      out.className = "small err";
      out.textContent = st.output ? "Sign-in did not start: " + st.output.slice(-200) : "No sign-in code yet. Run " + p.login_cmd + " on the Pi instead.";
      return;
    }
    out.className = "small";
    out.replaceChildren("Open ", safeLink(st.url, st.url), " and enter code ", h("strong", { class: "mono" }, st.code), ". Waiting…");
    for (let i = 0; i < 180 && st.running; i++) {
      await new Promise((r) => setTimeout(r, 5000));
      st = await api("/llm/providers/" + p.id + "/login");
    }
    if (!st.running && st.exit_code === 0) { toast("Signed in to " + p.label); showLLMSettings(); }
    else if (!st.running) { out.className = "small err"; out.textContent = "Sign-in failed or expired. Try again."; }
  } catch (e) { out.className = "small err"; out.textContent = e.message; }
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
