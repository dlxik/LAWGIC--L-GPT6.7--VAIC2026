// [P4] Logic dashboard. Khong framework, khong build step.

// ---------- theme (chay TRUOC render de tranh flash) ----------

const THEME_KEY = "lawgic-theme";
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem(THEME_KEY, t); } catch (_) {}
}
(function initTheme() {
  // Ep LUON LIGHT (dark dang xau) — bo qua localStorage/prefers-color-scheme.
  try { localStorage.setItem(THEME_KEY, "light"); } catch (_) {}
  document.documentElement.setAttribute("data-theme", "light");
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

// Nhãn + màu theo mức độ nghiêm trọng
function sevMeta(sev) {
  const s = ["HIGH", "MEDIUM", "LOW"].includes(sev) ? sev : "MEDIUM";
  return { HIGH: { cls: "high", label: "Nghiêm trọng" },
           MEDIUM: { cls: "med", label: "Trung bình" },
           LOW: { cls: "low", label: "Thấp" } }[s];
}

const _DOC_VI = {
  tncn2025: "Luật Thuế TNCN 2025", qlt2025: "Luật Quản lý thuế 2025",
  qlt2019: "Luật Quản lý thuế 2019",
};

// node_id "tncn2025-d7-k1-a" -> "Điều 7 · Khoản 1 · Điểm a — Luật Thuế TNCN 2025"
function formatCite(nodeId) {
  const parts = String(nodeId || "").split("-");
  const doc = _DOC_VI[parts[0]] || parts[0] || "";
  const bits = [];
  for (const p of parts.slice(1)) {
    if (/^d\d+$/.test(p)) bits.push("Điều " + p.slice(1));
    else if (/^k\d+$/.test(p)) bits.push("Khoản " + p.slice(1));
    else bits.push("Điểm " + p);
  }
  return { path: bits.join(" · "), doc };
}

// Rút số Điều duy nhất từ list node_id (cho chip "trái Điều X" trên card)
function articlesOf(nodeIds) {
  const arts = [];
  for (const nid of nodeIds || []) {
    const m = String(nid).match(/-d(\d+)/);
    if (m && !arts.includes(m[1])) arts.push(m[1]);
  }
  return arts;
}

function cardHtml(m) {
  const per24 = (m.velocity * 24).toFixed(0);
  const sv = sevMeta(m.severity);
  const arts = articlesOf(m.contradicts);
  const docLabel = m.contradicts && m.contradicts.length
    ? (_DOC_VI[String(m.contradicts[0]).split("-")[0]] || "") : "";
  const lawChip = arts.length
    ? `<span class="law-chip">⚖ Trái Điều ${arts.slice(0, 2).join(", ")}${arts.length > 2 ? " +" + (arts.length - 2) : ""}${docLabel ? " · " + escapeHtml(docLabel) : ""}</span>`
    : "";
  return `
    <article class="card sev-${sv.cls}" data-id="${escapeHtml(m.misconception_id)}" role="button" tabindex="0">
      <div class="card-bar"></div>
      <div class="card-main">
        <div class="card-top">
          <span class="sev-pill ${sv.cls}">${sv.label}</span>
          ${lawChip}
        </div>
        <div class="card-claim"><span class="quote-x">“</span>${escapeHtml(m.canonical_text)}<span class="quote-x">”</span></div>
        <div class="card-stats">
          <span title="Số lần xuất hiện"><b>${fmtNum(m.count)}</b> lần</span>
          <span title="Tổng tương tác"><b>${fmtNum(m.total_engagement)}</b> tương tác</span>
          <span title="Tốc độ lan"><b>~${per24}</b>/24h</span>
          <span class="card-cta">Xem chi tiết →</span>
        </div>
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
    const citations = d.contradicts.map(citationHtml).join("")
      || `<div class="loading">Không xác định được điều luật bị vi phạm.</div>`;
    const postsBlock = role() === "guest"
      ? `<div class="mc-section">
           <h4>💬 Bằng chứng lan truyền</h4>
           <div class="locked-panel" style="padding:24px 20px">
             <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
             <p style="margin:0">Đăng nhập để xem post minh họa gốc trên báo/mạng xã hội.</p>
           </div>
         </div>`
      : `<div class="mc-section"><h4>💬 Bằng chứng lan truyền <span class="mc-count">${(d.posts || []).length}</span></h4>${
          (d.posts || []).map(postHtml).join("") || `<div class="loading">Chưa nạp post minh họa.</div>`
        }</div>`;
    holder.innerHTML = `
      <div class="mc-contrast">
        <div class="mc-block wrong">
          <div class="mc-tag">✕ Đang lan truyền — SAI</div>
          <p>“${escapeHtml(m.canonical_text)}”</p>
        </div>
        <div class="mc-arrow" aria-hidden="true">→</div>
        <div class="mc-block right">
          <div class="mc-tag">✓ Đúng theo luật</div>
          <p>${escapeHtml(m.correction) || "<em>(chưa có đính chính)</em>"}</p>
        </div>
      </div>
      <div class="mc-section">
        <h4>⚖ Điều luật bị vi phạm <span class="mc-count">${d.contradicts.length}</span></h4>
        <div class="contradicts">${citations}</div>
      </div>
      ${postsBlock}
    `;
  } catch (e) {
    if (myToken !== _detailToken || !holder.isConnected) return;
    holder.innerHTML = `<div class="error">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function citationHtml(c) {
  const cite = formatCite(c.node_id);
  return `
    <div class="lawcard">
      <div class="lawcard-head">
        <div class="lawcard-cite">${escapeHtml(cite.path)}${cite.doc ? `<span class="lawcard-doc">${escapeHtml(cite.doc)}</span>` : ""}</div>
        <span class="lawcard-badge">${escapeHtml(c.node_label || "")}</span>
      </div>
      <div class="lawcard-text">${escapeHtml(c.text || "")}</div>
    </div>
  `;
}

function postHtml(p) {
  const dt = new Date(p.created_at).toLocaleDateString("vi-VN");
  return `
    <div class="post">
      <div class="post-quote">“${escapeHtml(p.content)}”</div>
      <div class="post-meta">
        <span class="post-plat">${escapeHtml(p.platform)}</span>
        <span>${escapeHtml(dt)}</span>
        <span>❤ ${fmtNum(p.engagement)}</span>
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
  // Vẽ đồ thị quan hệ quanh điều luật được trích dẫn đầu tiên
  const top = (r.citations || [])[0];
  renderSubgraph(top ? top.node_id : null);
}

// ---------- Đồ thị quan hệ (cytoscape) ----------

const NODE_COLORS = {
  Article: "#2563eb", Clause: "#0891b2", Point: "#0d9488", Penalty: "#dc2626",
  Obligation: "#d97706", Right: "#16a34a", Prohibition: "#b91c1c",
  Subject: "#7c3aed", Deadline: "#db2777", Exemption: "#059669",
  TaxRate: "#ca8a04", TaxBase: "#0284c7", LegalDocument: "#475569",
};
let cy = null;

function cyElements(data) {
  const els = [];
  const seen = new Set();
  for (const n of data.nodes) {
    if (seen.has(n.id)) continue;
    seen.add(n.id);
    els.push({ data: { id: n.id, label: n.display, type: n.label,
      vi: n.label_vi, center: n.is_center ? 1 : 0, full: n.text || "" } });
  }
  for (const e of data.edges) {
    els.push({ data: { id: `e_${e.source}__${e.target}__${e.type}`,
      source: e.source, target: e.target, label: e.type_vi } });
  }
  return els;
}

const CY_STYLE = [
  { selector: "node", style: {
    "background-color": (n) => NODE_COLORS[n.data("type")] || "#64748b",
    "label": "data(label)", "color": "#fff", "font-size": "12px",
    "text-valign": "center", "text-halign": "center", "text-wrap": "wrap",
    "text-max-width": "84px", "width": 56, "height": 56,
    "border-width": 3, "border-color": "#ffffff",
    "transition-property": "border-color, border-width", "transition-duration": "120ms" } },
  { selector: "node[center = 1]", style: {
    "border-width": 5, "border-color": "#facc15", "width": 74, "height": 74,
    "font-size": "13px", "font-weight": "bold" } },
  { selector: "edge", style: {
    "width": 2, "line-color": "#94a3b8", "target-arrow-color": "#94a3b8",
    "target-arrow-shape": "triangle", "arrow-scale": 1.1, "curve-style": "bezier",
    "label": "data(label)", "font-size": "10px", "color": "#64748b",
    "text-rotation": "autorotate", "text-background-color": "#ffffff",
    "text-background-opacity": 0.85, "text-background-padding": "3px" } },
];

function addToGraph(data) {
  for (const el of cyElements(data)) {
    if (cy.getElementById(el.data.id).length === 0) cy.add(el);
  }
}

async function renderSubgraph(nodeId) {
  const $g = $("#qa-graph");
  const setVis = (v) => { $g.hidden = !v; const r = $("#qa-result"); if (r) r.classList.toggle("has-graph", v); };
  if (!nodeId || typeof cytoscape === "undefined") { setVis(false); return; }
  let data;
  try { data = await api(`/graph/subgraph?node=${encodeURIComponent(nodeId)}&depth=2`); }
  catch (e) { setVis(false); return; }
  if (!data.nodes || !data.nodes.length) { setVis(false); return; }
  setVis(true);

  const cyBox = document.getElementById("cy");
  // Đợi 1 frame để container 2-cột có kích thước thật rồi mới đo & layout.
  await new Promise((r) => requestAnimationFrame(r));

  // Trải lại node LẤP KÍN khung theo cả 2 chiều: cose cho bố cục hữu cơ, sau đó remap toạ
  // độ về đúng ô chứa (zoom=1, pan=0) nên không còn dải trống trên/dưới hay hai bên.
  // Có kẹp mức giãn để không méo hình khi đồ thị quá rộng/hẹp so với khung.
  const runLayout = () => {
    const r = cyBox.getBoundingClientRect();
    const w = r.width > 40 ? r.width : 720, h = r.height > 40 ? r.height : 440;
    // Layout trong khung VUÔNG (side theo số node) -> cose cho bố cục cân, KHÔNG bị kéo dẹt
    // theo tỉ lệ ô chứa. Sau đó stretchFill giãn khối vuông này lấp kín ô thật (rộng > cao)
    // đều cả 2 chiều, không dồn cục, không dải trống.
    const side = Math.max(520, Math.sqrt(cy.nodes().length) * 96);
    cy.layout({ name: "cose", animate: false, fit: false,
      boundingBox: { x1: 0, y1: 0, w: side, h: side }, nodeRepulsion: 12000, idealEdgeLength: 130,
      nodeOverlap: 16, gravity: 0.2, componentSpacing: 110, coolingFactor: 0.95, numIter: 1200 }).run();
    stretchFill(w, h, 46);
  };

  const stretchFill = (w, h, pad) => {
    const nodes = cy.nodes();
    if (nodes.length < 2) { cy.zoom(1); cy.pan({ x: w / 2, y: h / 2 }); return; }
    const bb = nodes.boundingBox();
    if (!bb.w || !bb.h) return;
    let sx = (w - 2 * pad) / bb.w, sy = (h - 2 * pad) / bb.h;
    // kẹp tỉ lệ giãn 2 chiều để tránh méo (không cho 1 chiều giãn quá 2.3x chiều kia)
    const R = 2.3;
    if (sx > sy * R) sx = sy * R; else if (sy > sx * R) sy = sx * R;
    const offX = (w - bb.w * sx) / 2, offY = (h - bb.h * sy) / 2;
    nodes.positions((n) => {
      const p = n.position();
      return { x: offX + (p.x - bb.x1) * sx, y: offY + (p.y - bb.y1) * sy };
    });
    cy.zoom(1); cy.pan({ x: 0, y: 0 });
  };

  // Huỷ instance cũ trước khi tạo mới -> tránh rò cytoscape + canvas mồ côi tích lại
  // qua mỗi lần hỏi (mỗi câu hỏi vẽ lại graph). Không destroy = leak bộ nhớ theo phiên.
  if (cy) { try { cy.destroy(); } catch (_) {} cy = null; }
  cy = cytoscape({ container: cyBox, elements: cyElements(data), style: CY_STYLE });
  cy.resize();
  runLayout();

  // Container 2-cột có thể chưa đo đúng lúc init -> layout lại 1 nhịp sau; đổi kích thước
  // cửa sổ cũng layout lại theo khung mới (fit() thường sẽ để lại khoảng trống nên không dùng).
  const relayout = () => { if (cy) { cy.resize(); runLayout(); } };
  setTimeout(relayout, 260);
  if (!renderSubgraph._resizeBound) {
    renderSubgraph._resizeBound = true;
    let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(relayout, 150); });
  }

  // Click node -> đọc nội dung điều luật; click cạnh -> xem quan hệ (giống Neo4j Browser)
  cy.on("tap", "node", (evt) => showNodeDetail(evt.target));
  cy.on("tap", "edge", (evt) => showEdgeDetail(evt.target));

  const legendTypes = [...new Map(data.nodes.map((n) => [n.label, n.label_vi])).entries()];
  $("#cy-legend").innerHTML = legendTypes.map(([t, vi]) =>
    `<span class="cy-leg"><i style="background:${NODE_COLORS[t] || "#64748b"}"></i>${escapeHtml(vi)}</span>`).join("");

  // hiện sẵn node trung tâm khi mở
  const center = cy.nodes("[center = 1]");
  if (center.length) showNodeDetail(center[0]);
}

function showNodeDetail(n) {
  const text = n.data("full") || "(node này không có nội dung văn bản)";
  $("#cy-detail").innerHTML = `
    <div class="cy-detail-node">
      <div class="cy-detail-head">
        <span class="cy-detail-title">${escapeHtml(n.data("label"))}</span>
        <span class="cy-detail-badge" style="background:${NODE_COLORS[n.data("type")] || "#64748b"}">${escapeHtml(n.data("vi") || "")}</span>
        <button class="cy-expand-btn" data-expand="${escapeHtml(n.id())}">＋ Mở rộng quan hệ</button>
      </div>
      <div class="cy-detail-text">${escapeHtml(text)}</div>
      <div class="cy-detail-id">${escapeHtml(n.id())}</div>
    </div>`;
  const btn = $("#cy-detail").querySelector("[data-expand]");
  if (btn) btn.addEventListener("click", () => expandNode(btn.dataset.expand));
}

function showEdgeDetail(e) {
  $("#cy-detail").innerHTML = `
    <div class="cy-detail-edge">
      <span class="cy-detail-title">${escapeHtml(e.source().data("label"))}</span>
      <span class="cy-detail-rel">— ${escapeHtml(e.data("label"))} →</span>
      <span class="cy-detail-title">${escapeHtml(e.target().data("label"))}</span>
    </div>`;
}

async function expandNode(id) {
  const src = cy.getElementById(id);
  const base = src.length ? { ...src.position() } : { x: 0, y: 0 };
  let more;
  try { more = await api(`/graph/subgraph?node=${encodeURIComponent(id)}&depth=1`); }
  catch (e) { return; }

  // Node MỚI đặt thành vòng quanh node được click; node cũ GIỮ NGUYÊN vị trí
  // -> không re-layout toàn graph -> không giật/nhảy.
  const els = cyElements(more);
  const newNodes = els.filter((el) => !el.data.source && cy.getElementById(el.data.id).length === 0);
  const R = 130;
  newNodes.forEach((el, i) => {
    const ang = (2 * Math.PI * i) / Math.max(newNodes.length, 1);
    el.position = { x: base.x + R * Math.cos(ang), y: base.y + R * Math.sin(ang) };
  });
  cy.add(newNodes);
  els.forEach((el) => {
    if (el.data.source && cy.getElementById(el.data.id).length === 0) cy.add(el);
  });
  // chỉ zoom vừa khung, KHÔNG xáo vị trí node cũ
  cy.animate({ fit: { eles: cy.elements(), padding: 30 }, duration: 300, easing: "ease-out" });
}

// ---------- Search (Tra cuu van ban) ----------

const GUEST_SEARCH_CAP = 5;
const $searchForm    = $("#search-form");
const $searchInput   = $("#search-input");
const $searchMeta    = $("#search-meta");
const $searchResults = $("#search-results");

$searchForm.addEventListener("submit", (e) => {
  e.preventDefault();
  withBusy($searchForm, () => runSearch($searchInput.value.trim(), null));
});

let lastSearchQuery = "";
async function runSearch(q, asOf) {
  if (!q) return;
  lastSearchQuery = q;   // giữ để tô đậm từ khóa trong kết quả + trong điều luật gốc
  const isGuest = role() === "guest";
  const limit = isGuest ? GUEST_SEARCH_CAP : 30;
  if (isGuest) asOf = null;   // guest cam dung date filter
  const activeOnly = $("#search-active-only")?.checked;

  $searchMeta.hidden = true;
  $searchResults.innerHTML = `<div class="loading">Đang tra cứu…</div>`;
  try {
    const params = new URLSearchParams({ q, limit: String(limit) });
    if (asOf) params.set("as_of_date", asOf);
    if (activeOnly) params.set("active_only", "true");
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

const _SEARCH_STOP = new Set(["là","của","và","các","cho","có","không","được","về",
  "theo","đối","với","khi","hay","một","những","này","đó","thì","ở","trong","phải",
  "bao","nhiêu","như","thế","nào","gì","ra","sao"]);

function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

// Tô đậm từ khóa NGAY TRÊN chuỗi đã escape HTML (token là chữ/số nên an toàn).
function hlKeywords(escapedText, query) {
  const toks = (query || "").toLowerCase().match(/[0-9a-zà-ỹ]{2,}/giu) || [];
  const uniq = [...new Set(toks)].filter((t) => !_SEARCH_STOP.has(t));
  if (!uniq.length) return escapedText;
  uniq.sort((a, b) => b.length - a.length);  // cụm dài match trước
  const re = new RegExp("(" + uniq.map(escapeRegex).join("|") + ")", "giu");
  return escapedText.replace(re, "<mark>$1</mark>");
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
    <article class="result clickable" data-node="${escapeHtml(h.node_id)}" role="button" tabindex="0"
             title="Nhấn để đọc nguyên Điều luật gốc">
      <div class="result-head">
        <div class="result-cite">${escapeHtml(h.display)}</div>
        <div class="result-badges">
          ${badge}
          <span class="result-badge">${escapeHtml(h.node_label)}</span>
        </div>
      </div>
      <div class="result-body">${hlKeywords(escapeHtml(h.text), lastSearchQuery)}</div>
      <div class="result-foot">
        <div class="result-foot-left">
          <code>${escapeHtml(h.node_id)}</code>
          <span>${range}</span>
        </div>
        <span class="result-open">Đọc nguyên Điều →</span>
        ${downloadLinkHtml(h.node_id)}
      </div>
    </article>
  `;
}

// ---------- đọc NGUYÊN Điều luật gốc (modal) ----------

async function openLawModal(nodeId) {
  const modal = $("#law-modal");
  _modalReturnFocus = document.activeElement;
  $("#law-modal-head").innerHTML = `<div class="loading">Đang tải điều luật…</div>`;
  $("#law-modal-body").innerHTML = "";
  modal.hidden = false;
  try {
    const d = await api(`/law/article?node_id=${encodeURIComponent(nodeId)}`);
    renderArticle(d);
  } catch (e) {
    $("#law-modal-head").innerHTML = `<div class="error">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function renderArticle(d) {
  const a = d.article;
  const q = lastSearchQuery;
  const todayISO = new Date().toISOString().slice(0, 10);
  const expired = a.effective_to && a.effective_to <= todayISO;
  const badge = expired
    ? `<span class="result-badge expired">Hết hiệu lực${a.effective_to ? ` (đến ${escapeHtml(a.effective_to)})` : ""}</span>`
    : `<span class="result-badge active">Đang hiệu lực</span>`;
  $("#law-modal-head").innerHTML = `
    <div class="law-doc">${escapeHtml(a.doc_number)}</div>
    <h3 id="law-title" class="law-title">${escapeHtml(a.display)}${a.heading ? ` — ${escapeHtml(a.heading)}` : ""}</h3>
    <div class="law-badges">${badge}${a.effective_from ? `<span class="law-eff">hiệu lực từ ${escapeHtml(a.effective_from)}</span>` : ""}</div>
  `;
  const rows = d.items
    .filter((it) => it.label !== "Article")   // tiêu đề Điều đã ở head
    .map((it) => {
      const tgt = it.is_target ? " target" : "";
      const label = it.label === "Clause" ? `Khoản ${escapeHtml(it.num)}.` : `${escapeHtml(it.num)})`;
      const txt = hlKeywords(escapeHtml(it.text || it.heading || ""), q);
      return `<div class="law-item depth-${it.depth}${tgt}"><span class="law-num">${label}</span> <span class="law-text">${txt}</span></div>`;
    }).join("");
  $("#law-modal-body").innerHTML = rows || `<div class="loading">Điều luật không có nội dung chi tiết.</div>`;
  setTimeout(() => {
    const t = $("#law-modal-body .law-item.target");
    if (t) t.scrollIntoView({ block: "center", behavior: "smooth" });
  }, 30);
}

function closeLawModal() {
  const m = $("#law-modal");
  if (m.hidden) return;
  m.hidden = true;
  if (_modalReturnFocus && typeof _modalReturnFocus.focus === "function") {
    _modalReturnFocus.focus();
    _modalReturnFocus = null;
  }
}

// Nhấn 1 kết quả -> bung nguyên Điều (bỏ qua khi bấm link tải .docx)
$searchResults.addEventListener("click", (e) => {
  if (e.target.closest("a")) return;
  const card = e.target.closest(".result[data-node]");
  if (card) openLawModal(card.dataset.node);
});
$searchResults.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const card = e.target.closest(".result[data-node]");
  if (card) { e.preventDefault(); openLawModal(card.dataset.node); }
});
$$("#law-modal [data-close]").forEach((el) => el.addEventListener("click", closeLawModal));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("#law-modal").hidden) closeLawModal();
});
$("#search-active-only")?.addEventListener("change", () => {
  if (lastSearchQuery) runSearch(lastSearchQuery, null);
});

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

  // Guest khong duoc dung date filter -> disable input
  ["#qa-date"].forEach((sel) => {
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
// Nut "Đăng nhập để tiếp tục" (vd. panel het luot hoi cua Khach) -> mo modal dang nhap
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-open=\"signin\"]");
  if (t) openModal();
});

// ---------- boot ----------

// Da khoa LIGHT: nut toggle giu nguyen light, khong cho sang dark.
$("#theme-toggle").addEventListener("click", () => {
  applyTheme("light");
});

renderAuth();
applyRoleGates();

loadStats();
loadTrends();
