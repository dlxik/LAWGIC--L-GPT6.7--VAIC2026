// [P4] Logic dashboard. Khong framework, khong build step.

// Origin thay doi tuy noi mo:
//   - Mo qua /static (uvicorn serve) -> API cung origin
//   - Mo file://       -> tro sang localhost:8000
const API = (location.origin && location.origin.startsWith("http"))
  ? location.origin
  : "http://localhost:8000";

document.getElementById("api-url").textContent = API;

// ---------- helpers ----------

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const escapeHtml = (s) => String(s ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json();
}

const fmtNum = (n) => new Intl.NumberFormat("vi-VN").format(n);

// ---------- tabs ----------

$$("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    $$("nav button").forEach((b) => {
      const on = b === btn;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    $$("body > section").forEach((s) => { s.hidden = s.id !== tab; });
    if (tab === "diff" && !diffLoaded) loadDiff("qlt2025");
  });
});

// ---------- stats + source badge ----------

async function loadStats() {
  try {
    const [health, s] = await Promise.all([api("/health"), api("/stats")]);
    const badge = $("#source-badge");
    badge.textContent = health.graph_source;
    badge.className = "badge " + health.graph_source;

    $("#stats").innerHTML = `
      <div class="stat"><b>${fmtNum(s.documents)}</b>Van ban</div>
      <div class="stat"><b>${fmtNum(s.points)}</b>Diem</div>
      <div class="stat"><b>${fmtNum(s.posts_analysed)}</b>Post da phan tich</div>
      <div class="stat"><b>${fmtNum(s.misconceptions_active)}</b>Canh bao</div>
      <div class="stat"><b>${fmtNum(s.total_engagement_flagged)}</b>Tuong tac gan co</div>
    `;
  } catch (e) {
    $("#stats").innerHTML = `<div class="error">Khong ket noi API: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------- trends ----------

const $trends = $("#trends-list");
const $detail = $("#misc-detail");

async function loadTrends() {
  $trends.innerHTML = `<div class="loading">Dang tai canh bao...</div>`;
  try {
    const items = await api("/trends");
    if (!items.length) {
      $trends.innerHTML = `<div class="loading">Chua co canh bao nao.</div>`;
      return;
    }
    $trends.innerHTML = items.map(cardHtml).join("");
    $$(".card", $trends).forEach((c) => {
      c.addEventListener("click", () => showMisconception(c.dataset.id));
    });
  } catch (e) {
    $trends.innerHTML = `<div class="error">Loi tai trend: ${escapeHtml(e.message)}</div>`;
  }
}

function cardHtml(m) {
  const per24 = (m.velocity * 24).toFixed(0);
  return `
    <article class="card" data-id="${escapeHtml(m.misconception_id)}">
      <div class="sev ${escapeHtml(m.severity)}">${escapeHtml(m.severity)}</div>
      <div class="canonical">"${escapeHtml(m.canonical_text)}"</div>
      <div class="meta">
        <span><b>${fmtNum(m.count)}</b> lan lap</span>
        <span><b>${fmtNum(m.total_engagement)}</b> tuong tac</span>
        <span><b>~${per24}</b>/24h</span>
      </div>
    </article>
  `;
}

async function showMisconception(id) {
  $detail.hidden = false;
  $detail.innerHTML = `<div class="loading">Dang tai chi tiet...</div>`;
  $detail.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const d = await api(`/misconception/${encodeURIComponent(id)}`);
    const m = d.misconception;
    const citations = d.contradicts.map(citationHtml).join("");
    const posts = (d.posts || []).map(postHtml).join("") || `<div class="loading">Chua nap post minh hoa.</div>`;
    $detail.innerHTML = `
      <h3>"${escapeHtml(m.canonical_text)}"</h3>
      <div class="correction"><strong>Dinh chinh:</strong> ${escapeHtml(m.correction)}</div>
      <h4>Dieu luat bi hieu sai</h4>
      <div class="contradicts">${citations}</div>
      <div class="posts"><h4>Post minh hoa</h4>${posts}</div>
    `;
  } catch (e) {
    $detail.innerHTML = `<div class="error">Loi: ${escapeHtml(e.message)}</div>`;
  }
}

function citationHtml(c) {
  return `
    <div class="citation">
      <div class="cite-head">
        <span>${escapeHtml(c.display)}</span>
        <span class="conf">${c.confidence != null ? `confidence ${(c.confidence*100).toFixed(0)}%` : ""}</span>
      </div>
      <div class="cite-text">${escapeHtml(c.text)}</div>
      <div class="cite-id">${escapeHtml(c.node_id)}</div>
    </div>
  `;
}

function postHtml(p) {
  const dt = new Date(p.created_at).toLocaleString("vi-VN");
  return `
    <div class="post">
      <div>"${escapeHtml(p.content)}"</div>
      <div class="meta-row">
        ${escapeHtml(p.platform)} — ${escapeHtml(dt)} — tuong tac ${fmtNum(p.engagement)} — <code>${escapeHtml(p.author_hash)}</code>
      </div>
    </div>
  `;
}

$("#refresh-trends").addEventListener("click", () => { loadTrends(); loadStats(); });

// ---------- Q&A ----------

const $qaAnswer = $("#qa-answer");
const $qaForm   = $("#qa-form");
const $qaInput  = $("#qa-input");
const $qaDate   = $("#qa-date");

$qaForm.addEventListener("submit", (e) => {
  e.preventDefault();
  askQuestion($qaInput.value.trim(), $qaDate.value || null);
});

$$(".qa-samples button").forEach((b) => {
  b.addEventListener("click", () => {
    $qaInput.value = b.dataset.sample;
    $qaInput.focus();
  });
});

async function askQuestion(question, asOfDate) {
  if (!question) return;
  $qaAnswer.hidden = false;
  $qaAnswer.innerHTML = `<div class="loading">Dang tra loi...</div>`;
  try {
    const r = await api("/qa", {
      method: "POST",
      body: JSON.stringify({ question, as_of_date: asOfDate }),
    });
    renderAnswer(r);
  } catch (e) {
    $qaAnswer.innerHTML = `<div class="error">Loi: ${escapeHtml(e.message)}</div>`;
  }
}

function renderAnswer(r) {
  const cites = (r.citations || []).map(citationHtml).join("")
    || `<div class="loading">Khong co citation.</div>`;
  $qaAnswer.innerHTML = `
    <h4>Cau tra loi <span class="mode ${r.mode}">${r.mode.toUpperCase()}</span></h4>
    <div class="body">${escapeHtml(r.answer)}</div>
    <h4>Trich dan Dieu &mdash; Khoan &mdash; Diem
      ${r.confidence != null ? `<span style="text-transform:none;color:var(--muted)"> — confidence ${(r.confidence*100).toFixed(0)}%</span>` : ""}
    </h4>
    ${cites}
  `;
}

// ---------- Diff ----------

let diffLoaded = false;
async function loadDiff(docId) {
  const $list = $("#diff-list");
  $list.innerHTML = `<div class="loading">Dang tai...</div>`;
  try {
    const d = await api(`/document/${encodeURIComponent(docId)}/diff`);
    $("#diff-doc-title").textContent = `${d.document.doc_number} — ${d.document.title}`;
    if (!d.diffs.length) {
      $list.innerHTML = `<div class="loading">Van ban nay khong co diff.</div>`;
    } else {
      $list.innerHTML = d.diffs.map(diffHtml).join("");
    }
    diffLoaded = true;
  } catch (e) {
    $list.innerHTML = `<div class="error">Loi: ${escapeHtml(e.message)}</div>`;
  }
}

function diffHtml(d) {
  const oldSide = d.old_point
    ? `<div class="side old"><h5>Van ban cu — ${escapeHtml(d.old_point.display)}</h5>${escapeHtml(d.old_point.text)}</div>`
    : `<div class="side old empty">(Diem moi hoan toan, khong co ban cu)</div>`;
  const newSide = d.new_point
    ? `<div class="side new"><h5>Van ban moi — ${escapeHtml(d.new_point.display)}</h5>${escapeHtml(d.new_point.text)}</div>`
    : `<div class="side new empty">(Diem cu bi xoa, khong co ban moi)</div>`;
  return `
    <div class="diff-row">
      <div class="change">${escapeHtml(d.change_type)} · similarity ${(d.similarity*100).toFixed(0)}% · tu ${escapeHtml(d.effective_from)}</div>
      <div class="sides">${oldSide}${newSide}</div>
      <div class="summary">${escapeHtml(d.summary)}</div>
    </div>
  `;
}

// ---------- boot ----------

loadStats();
loadTrends();
