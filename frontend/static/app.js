// [P4] Logic dashboard. Khong framework, khong build step.

// ---------- theme (chay TRUOC render de tranh flash) ----------

const THEME_KEY = "lawgic-theme";
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem(THEME_KEY, t); } catch (_) {}
}
(function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch (_) {}
  const prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  const initial = saved || (prefersLight ? "light" : "dark");
  document.documentElement.setAttribute("data-theme", initial);
})();

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

function activateTab(btn) {
  const tab = btn.dataset.tab;
  $$(".sidebar-nav button").forEach((b) => {
    const on = b === btn;
    b.classList.toggle("active", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
    b.setAttribute("tabindex", on ? "0" : "-1");
  });
  $$("main > section").forEach((s) => { s.hidden = s.id !== tab; });
  if (tab === "diff" && !diffLoaded && role() !== "guest") loadDiff("qlt2025");
}

$$(".sidebar-nav button").forEach((btn) => {
  btn.addEventListener("click", () => activateTab(btn));
});

// Keyboard nav: arrow keys move focus + activate; Home/End go to first/last
$(".sidebar-nav").addEventListener("keydown", (e) => {
  const btns = $$(".sidebar-nav button");
  const idx = btns.indexOf(document.activeElement);
  if (idx < 0) return;
  let next = null;
  if (e.key === "ArrowDown" || e.key === "ArrowRight") next = btns[(idx + 1) % btns.length];
  else if (e.key === "ArrowUp" || e.key === "ArrowLeft") next = btns[(idx - 1 + btns.length) % btns.length];
  else if (e.key === "Home") next = btns[0];
  else if (e.key === "End") next = btns[btns.length - 1];
  if (next) {
    e.preventDefault();
    next.focus();
    activateTab(next);
  }
});

// ---------- stats + source badge ----------

async function loadStats() {
  try {
    const [health, s] = await Promise.all([api("/health"), api("/stats")]);

    $("#source-badge").textContent = health.graph_source;
    const dot = $("#source-dot");
    if (dot) dot.className = "status-dot " + health.graph_source;

    $("#stats").innerHTML = `
      <div class="stat"><span>Văn bản</span><b>${fmtNum(s.documents)}</b></div>
      <div class="stat"><span>Điểm / khoản / điều</span><b>${fmtNum(s.points)}</b></div>
      <div class="stat"><span>Post phân tích</span><b>${fmtNum(s.posts_analysed)}</b></div>
      <div class="stat"><span>Cảnh báo đang hoạt động</span><b>${fmtNum(s.misconceptions_active)}</b></div>
      <div class="stat"><span>Tương tác gắn cờ</span><b>${fmtNum(s.total_engagement_flagged)}</b></div>
    `;
  } catch (e) {
    $("#stats").innerHTML = `<div class="error">Không kết nối được API: ${escapeHtml(e.message)}</div>`;
  }
}

// ---------- trends ----------

const $trends = $("#trends-list");

async function loadTrends() {
  $trends.innerHTML = `<div class="loading">Đang tải cảnh báo…</div>`;
  const $count = $("#trends-count");
  if ($count) $count.textContent = "";
  try {
    const items = await api("/trends");
    if (!items.length) {
      $trends.innerHTML = `<div class="loading">Chưa có cảnh báo nào.</div>`;
      return;
    }
    if ($count) $count.textContent = `${items.length} trend`;
    $trends.innerHTML = items.map(cardHtml).join("");
    $$(".card", $trends).forEach((c) => {
      c.setAttribute("role", "button");
      c.setAttribute("tabindex", "0");
      c.addEventListener("click", () => showMisconception(c.dataset.id));
      c.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          showMisconception(c.dataset.id);
        }
      });
    });
  } catch (e) {
    $trends.innerHTML = `<div class="error">Lỗi tải trend: ${escapeHtml(e.message)}</div>`;
  }
}

function cardHtml(m) {
  const per24 = (m.velocity * 24).toFixed(0);
  const sev = ["HIGH", "MEDIUM", "LOW"].includes(m.severity) ? m.severity : "MEDIUM";
  return `
    <article class="card" data-id="${escapeHtml(m.misconception_id)}">
      <div class="title-row">
        <div class="canonical">"${escapeHtml(m.canonical_text)}"</div>
        <div class="sev ${sev}">${sev}</div>
      </div>
      <div class="meta">
        <span><b>${fmtNum(m.count)}</b> lần lặp</span>
        <span><b>${fmtNum(m.total_engagement)}</b> tương tác</span>
        <span><b>~${per24}</b>/24h</span>
      </div>
    </article>
  `;
}

let _detailToken = 0;
function closeAllDetails() {
  $$(".card-detail", $trends).forEach((el) => el.remove());
  $$(".card.active", $trends).forEach((el) => el.classList.remove("active"));
}

async function showMisconception(id) {
  const card = $trends.querySelector(`.card[data-id="${CSS.escape(id)}"]`);
  if (!card) return;

  // Toggle: bam lai chinh card dang mo -> dong
  if (card.classList.contains("active")) {
    closeAllDetails();
    return;
  }

  closeAllDetails();
  card.classList.add("active");

  // Token de tranh race: neu user click card khac giua chung, cai holder cu
  // duoc thay the va ket qua fetch cu KHONG duoc ghi vao holder moi.
  const myToken = ++_detailToken;
  const holder = document.createElement("div");
  holder.className = "card-detail";
  holder.innerHTML = `<div class="loading">Đang tải chi tiết…</div>`;
  card.after(holder);
  holder.scrollIntoView({ behavior: "smooth", block: "nearest" });

  try {
    const d = await api(`/misconception/${encodeURIComponent(id)}`);
    if (myToken !== _detailToken || !holder.isConnected) return;  // stale
    const m = d.misconception;
    const citations = d.contradicts.map(citationHtml).join("");
    const postsBlock = role() === "guest"
      ? `<div class="posts">
           <h4>Post minh họa</h4>
           <div class="locked-panel" style="padding:24px 20px">
             <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
             <p style="margin:0">Đăng nhập để xem post minh họa gốc trên báo/mạng xã hội.</p>
           </div>
         </div>`
      : `<div class="posts"><h4>Post minh họa</h4>${
          (d.posts || []).map(postHtml).join("") || `<div class="loading">Chưa nạp post minh họa.</div>`
        }</div>`;
    holder.innerHTML = `
      <div class="correction"><strong>Đính chính:</strong> ${escapeHtml(m.correction)}</div>
      <h4>Điều luật bị hiểu sai</h4>
      <div class="contradicts">${citations}</div>
      ${postsBlock}
    `;
  } catch (e) {
    if (myToken !== _detailToken || !holder.isConnected) return;
    holder.innerHTML = `<div class="error">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function citationHtml(c) {
  return `
    <div class="citation">
      <div class="cite-head">
        <span>${escapeHtml(c.display)}</span>
        <span class="conf">${c.confidence != null ? `độ tin cậy ${(c.confidence*100).toFixed(0)}%` : ""}</span>
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
        ${escapeHtml(p.platform)} — ${escapeHtml(dt)} — tương tác ${fmtNum(p.engagement)} — <code>${escapeHtml(p.author_hash)}</code>
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
  withBusy($qaForm, () => askQuestion($qaInput.value.trim(), $qaDate.value || null));
});

async function withBusy(form, fn) {
  const btn = form.querySelector("button[type=submit]");
  if (!btn || btn.disabled) return;  // dang chay -> bo qua click thu 2
  btn.disabled = true;
  try { await fn(); }
  finally { btn.disabled = false; }
}

$$(".qa-samples button").forEach((b) => {
  b.addEventListener("click", () => {
    $qaInput.value = b.dataset.sample;
    $qaInput.focus();
  });
});

async function askQuestion(question, asOfDate) {
  if (!question) return;

  // Guest quota gate — 5 cau/session
  if (role() === "guest" && guestAskCount >= GUEST_QUOTA) {
    $qaAnswer.hidden = false;
    $qaAnswer.innerHTML = `
      <div class="locked-panel">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <h3>Đã hết lượt hỏi cho chế độ Khách</h3>
        <p>Chế độ Khách giới hạn ${GUEST_QUOTA} câu hỏi/phiên. Đăng nhập để tiếp tục hỏi không giới hạn và dùng bộ lọc <em>Hiệu lực tính đến ngày</em>.</p>
        <button class="primary-btn" data-open="signin">Đăng nhập để tiếp tục</button>
      </div>
    `;
    $qaAnswer.querySelector("[data-open]").addEventListener("click", openModal);
    return;
  }
  if (role() === "guest") {
    asOfDate = null;  // guest khong duoc dung date filter
    guestAskCount++;
    writeGuestAskCount(guestAskCount);
    renderGuestQuota();
  }

  $qaAnswer.hidden = false;
  $qaAnswer.innerHTML = `<div class="loading">Đang trả lời…</div>`;
  try {
    const r = await api("/qa", {
      method: "POST",
      body: JSON.stringify({ question, as_of_date: asOfDate }),
    });
    renderAnswer(r);
  } catch (e) {
    $qaAnswer.innerHTML = `<div class="error">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function renderAnswer(r) {
  const cites = (r.citations || []).map(citationHtml).join("")
    || `<div class="loading">Không có trích dẫn.</div>`;
  // Chi cho phep mode trong whitelist -> vua chan XSS vua tranh CSS class rac
  const modeRaw = String(r.mode || "").toLowerCase();
  const mode = ["llm", "template", "refused"].includes(modeRaw) ? modeRaw : "template";
  $qaAnswer.innerHTML = `
    <h4>Câu trả lời <span class="mode ${mode}">${mode.toUpperCase()}</span></h4>
    <div class="body">${escapeHtml(r.answer)}</div>
    <h4>Trích dẫn Điều &mdash; Khoản &mdash; Điểm
      ${r.confidence != null ? `<span style="text-transform:none;color:var(--ink-dim)"> — độ tin cậy ${(r.confidence*100).toFixed(0)}%</span>` : ""}
    </h4>
    ${cites}
  `;
}

// ---------- Search (Tra cuu van ban) ----------

const GUEST_SEARCH_CAP = 5;
const $searchForm    = $("#search-form");
const $searchInput   = $("#search-input");
const $searchDate    = $("#search-date");
const $searchMeta    = $("#search-meta");
const $searchResults = $("#search-results");

$searchForm.addEventListener("submit", (e) => {
  e.preventDefault();
  withBusy($searchForm, () => runSearch($searchInput.value.trim(), $searchDate.value || null));
});

async function runSearch(q, asOf) {
  if (!q) return;
  const isGuest = role() === "guest";
  const limit = isGuest ? GUEST_SEARCH_CAP : 30;
  if (isGuest) asOf = null;   // guest cam dung date filter

  $searchMeta.hidden = true;
  $searchResults.innerHTML = `<div class="loading">Đang tra cứu…</div>`;
  try {
    const params = new URLSearchParams({ q, limit: String(limit) });
    if (asOf) params.set("as_of_date", asOf);
    const r = await api(`/search?${params.toString()}`);
    renderSearchResults(r, isGuest);
  } catch (e) {
    $searchResults.innerHTML = `<div class="error">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function renderSearchResults(r, isGuest) {
  const shown = r.results.length;
  const capped = isGuest && r.total > GUEST_SEARCH_CAP;

  $searchMeta.hidden = false;
  $searchMeta.innerHTML = `
    <span class="search-count">${fmtNum(r.total)} kết quả</span>
    <span>từ khóa <code>"${escapeHtml(r.query)}"</code></span>
    ${r.as_of_date ? `<span>· hiệu lực ${escapeHtml(r.as_of_date)}</span>` : ""}
    ${capped ? `<span class="search-cap">· Khách xem ${shown}/${fmtNum(r.total)} — đăng nhập để xem đầy đủ</span>` : ""}
  `;

  if (!r.results.length) {
    $searchResults.innerHTML = `<div class="loading">Không tìm thấy điều luật nào khớp.</div>`;
    return;
  }
  $searchResults.innerHTML = r.results.map(resultHtml).join("");
}

function docIdFromNodeId(nodeId) {
  // "qlt2025-d25-k1-a" -> "qlt2025"; empty if malformed
  const idx = nodeId.indexOf("-");
  return idx > 0 ? nodeId.slice(0, idx) : "";
}

function downloadLinkHtml(nodeId) {
  const doc = docIdFromNodeId(nodeId);
  if (!doc) return "";
  return `
    <a class="doc-download" href="${API}/documents/${encodeURIComponent(doc)}/file" download title="Tải văn bản gốc (.docx)">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
      Tải văn bản gốc
    </a>
  `;
}

function resultHtml(h) {
  const todayISO = new Date().toISOString().slice(0, 10);
  const isExpired = h.effective_to && h.effective_to <= todayISO;
  const badge = isExpired
    ? `<span class="result-badge expired">Hết hiệu lực</span>`
    : `<span class="result-badge active">Đang hiệu lực</span>`;
  const range = h.effective_from
    ? `hiệu lực từ ${escapeHtml(h.effective_from)}${h.effective_to ? ` đến ${escapeHtml(h.effective_to)}` : ""}`
    : "";
  return `
    <article class="result">
      <div class="result-head">
        <div class="result-cite">${escapeHtml(h.display)}</div>
        <div class="result-badges">
          ${badge}
          <span class="result-badge">${escapeHtml(h.node_label)}</span>
        </div>
      </div>
      <div class="result-body">${escapeHtml(h.text)}</div>
      <div class="result-foot">
        <div class="result-foot-left">
          <code>${escapeHtml(h.node_id)}</code>
          <span>${range}</span>
        </div>
        ${downloadLinkHtml(h.node_id)}
      </div>
    </article>
  `;
}

// ---------- Diff ----------

let diffLoaded = false;
async function loadDiff(docId) {
  const $list = $("#diff-list");
  $list.innerHTML = `<div class="loading">Đang tải…</div>`;
  try {
    const d = await api(`/document/${encodeURIComponent(docId)}/diff`);
    $("#diff-doc-title").textContent = `${d.document.doc_number} — ${d.document.title}`;
    if (!d.diffs.length) {
      $list.innerHTML = `<div class="loading">Văn bản này không có diff.</div>`;
    } else {
      $list.innerHTML = d.diffs.map(diffHtml).join("");
    }
    diffLoaded = true;
  } catch (e) {
    $list.innerHTML = `<div class="error">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function diffHtml(d) {
  const oldSide = d.old_point
    ? `<div class="side old"><h5>Văn bản cũ — ${escapeHtml(d.old_point.display)}</h5>${escapeHtml(d.old_point.text)}</div>`
    : `<div class="side old empty">(Điểm mới hoàn toàn, không có bản cũ)</div>`;
  const newSide = d.new_point
    ? `<div class="side new"><h5>Văn bản mới — ${escapeHtml(d.new_point.display)}</h5>${escapeHtml(d.new_point.text)}</div>`
    : `<div class="side new empty">(Điểm cũ bị xóa, không có bản mới)</div>`;
  return `
    <div class="diff-row">
      <div class="change">${escapeHtml(d.change_type)} · độ tương đồng ${(d.similarity*100).toFixed(0)}% · từ ${escapeHtml(d.effective_from)}</div>
      <div class="sides">${oldSide}${newSide}</div>
      <div class="summary">${escapeHtml(d.summary)}</div>
    </div>
  `;
}

// ---------- auth (fake, client-side) ----------

const AUTH_KEY = "lawgic-auth";
const GUEST_QUOTA_KEY = "lawgic-guest-asks";
const GUEST_QUOTA = 5;

function readGuestAskCount() {
  try {
    const n = parseInt(localStorage.getItem(GUEST_QUOTA_KEY) || "0", 10);
    return Number.isFinite(n) && n >= 0 ? n : 0;
  } catch { return 0; }
}
function writeGuestAskCount(n) {
  try { localStorage.setItem(GUEST_QUOTA_KEY, String(n)); } catch {}
}
let guestAskCount = readGuestAskCount();

function currentAuth() {
  try { return JSON.parse(localStorage.getItem(AUTH_KEY) || "null"); }
  catch { return null; }
}
function setAuth(a) {
  if (a) localStorage.setItem(AUTH_KEY, JSON.stringify(a));
  else localStorage.removeItem(AUTH_KEY);
  renderAuth();
  applyRoleGates();
}
function role() {
  const a = currentAuth();
  return a ? a.role : "guest";
}
function signIn(email, password) {
  if (!email || !password) return false;
  const isAdmin = /admin/i.test(email);
  setAuth({ email, role: isAdmin ? "admin" : "user", since: new Date().toISOString() });
  return true;
}
function signOut() {
  guestAskCount = 0;
  setAuth(null);
}

function renderAuth() {
  const widget = $("#auth-widget");
  const a = currentAuth();
  if (!a) {
    widget.innerHTML = `
      <div class="auth-guest">
        <div class="auth-label">Đang xem với vai trò</div>
        <div class="auth-value">Khách <span class="guest-quota" id="guest-quota"></span></div>
        <button id="btn-signin">Đăng nhập</button>
      </div>
    `;
    $("#btn-signin").addEventListener("click", openModal);
    renderGuestQuota();
  } else {
    const roleLabel = a.role === "admin" ? "Quản trị" : "Người dùng";
    widget.innerHTML = `
      <div class="auth-user">
        <div class="auth-avatar">${escapeHtml((a.email && a.email[0] || "?").toUpperCase())}</div>
        <div class="auth-info">
          <div class="auth-email">${escapeHtml(a.email)}</div>
          <div class="auth-role ${a.role}">${roleLabel}</div>
        </div>
        <button class="btn-signout" id="btn-signout" title="Đăng xuất" aria-label="Đăng xuất">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
        </button>
      </div>
    `;
    $("#btn-signout").addEventListener("click", signOut);
  }
}
function renderGuestQuota() {
  const el = $("#guest-quota");
  if (!el) return;
  const left = Math.max(0, GUEST_QUOTA - guestAskCount);
  el.textContent = `· còn ${left}/${GUEST_QUOTA} câu`;
  el.classList.toggle("exhausted", left === 0);
}

function applyRoleGates() {
  const r = role();
  document.body.dataset.role = r;

  // Diff tab: guest -> locked, khac -> mo. Neu vua sign-in va dang o diff -> load
  const lock = $("#diff-lock");
  const diffList = $("#diff-list");
  if (lock && diffList) {
    lock.hidden = r !== "guest";
    diffList.style.display = r === "guest" ? "none" : "";
    const diffTabOpen = document.querySelector("#diff") && !document.querySelector("#diff").hidden;
    if (r !== "guest" && diffTabOpen && !diffLoaded) loadDiff("qlt2025");
  }

  // Guest khong duoc dung date filter -> disable input
  ["#qa-date", "#search-date"].forEach((sel) => {
    const el = $(sel);
    if (!el) return;
    el.disabled = r === "guest";
    el.title = r === "guest" ? "Đăng nhập để dùng bộ lọc theo ngày" : "";
  });
}

let _modalReturnFocus = null;
function openModal() {
  const m = $("#signin-modal");
  if (!m.hidden) return;
  _modalReturnFocus = document.activeElement;
  m.hidden = false;
  // Focus vao email ngay khi modal hien -- setTimeout de sau reflow
  setTimeout(() => $("#signin-email")?.focus(), 0);
}
function closeModal() {
  const m = $("#signin-modal");
  if (m.hidden) return;
  m.hidden = true;
  if (_modalReturnFocus && typeof _modalReturnFocus.focus === "function") {
    _modalReturnFocus.focus();
    _modalReturnFocus = null;
  }
}

$$("#signin-modal [data-close]").forEach(el => el.addEventListener("click", closeModal));
$("#signin-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const email = $("#signin-email").value.trim();
  const pw = $("#signin-password").value;
  if (signIn(email, pw)) {
    closeModal();
    $("#signin-form").reset();
    guestAskCount = 0;
    writeGuestAskCount(0);
  }
});
document.addEventListener("keydown", (e) => {
  const modal = $("#signin-modal");
  if (modal.hidden) return;
  if (e.key === "Escape") { closeModal(); return; }
  if (e.key === "Tab") {
    // Focus trap: Tab quanh cac phan tu focusable trong modal
    const focusables = $$(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])",
      modal
    ).filter((el) => !el.disabled && el.offsetParent !== null);
    if (!focusables.length) return;
    const first = focusables[0], last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  }
});
// "Đăng nhập để mở khóa" trong locked panel cua diff tab
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-open=\"signin\"]");
  if (t) openModal();
});

// ---------- boot ----------

$("#theme-toggle").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(cur === "dark" ? "light" : "dark");
});

renderAuth();
applyRoleGates();

loadStats();
loadTrends();
