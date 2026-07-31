// Hyper A D2C Meta Ads Audit Engine -- frontend logic (vanilla JS, no build step)

const state = {
  meta: null,
  companies: [],
  sort: "opportunity_score",
  dir: "desc",
  currentEditId: null,
};

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function qs(id) { return document.getElementById(id); }

function toast(msg) {
  const t = qs("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2200);
}

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function tierBadge(tier) {
  return `<span class="badge tier-${esc(tier)}">${esc(tier)}</span>`;
}

function tag(text, cls) {
  return `<span class="tag ${cls || ""}">${esc(text)}</span>`;
}

function freshnessTag(v) {
  if (v === "Fresh") return tag(v, "tag-good");
  if (v === "Aging") return tag(v, "tag-warn");
  if (v === "Stale") return tag(v, "tag-bad");
  if (v === "No ads running") return tag(v, "tag-muted");
  return tag(v || "Not verified", "tag-muted");
}

function discountTag(v) {
  if (v === "Extreme (50%+)") return tag(v, "tag-bad");
  if (v === "Heavy (36-50%)") return tag(v, "tag-warn");
  if (v === "Moderate (16-35%)") return tag(v, "tag-warn");
  if (v === "None-light (0-15%)") return tag(v, "tag-good");
  if (v === "None visible") return tag(v, "tag-good");
  return tag(v || "Not audited", "tag-muted");
}

function convTag(v) {
  if (v === "Strong") return tag(v, "tag-good");
  if (v === "Partial") return tag(v, "tag-warn");
  if (v === "Weak") return tag(v, "tag-bad");
  return tag(v || "Not audited", "tag-muted");
}

function auditTag(v) {
  if (v === "Fully audited") return tag(v, "tag-good");
  if (v === "Partially audited") return tag(v, "tag-warn");
  return tag(v || "Needs audit", "tag-bad");
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    qs("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "pipeline") renderPipeline();
    if (btn.dataset.tab === "segmentation") renderSegmentation();
    if (btn.dataset.tab === "scoring") renderScoring();
  });
});

// ---------------------------------------------------------------------------
// Meta / filters
// ---------------------------------------------------------------------------

async function loadMeta() {
  const res = await fetch("/api/meta");
  state.meta = await res.json();
  fillSelect("f-industry", state.meta.industries, "Industry (all)");
  fillSelect("f-segment", state.meta.segments, "Segment (all)");
  fillSelect("f-tier", state.meta.score_tiers, "Tier (all)");
  fillSelect("f-stage", state.meta.pipeline_stages, "Pipeline stage (all)");
  fillSelect("f-adbucket", state.meta.meta_ad_count_buckets, "Meta ad volume (all)");
  fillSelect("f-discount", state.meta.discount_depth_buckets, "Discount depth (all)");
  fillSelect("f-audit", state.meta.audit_completeness_values, "Audit completeness (all)");
  fillSelect("edit-pipeline_stage", state.meta.pipeline_stages, null);
  fillSelect("edit-segment", state.meta.segments, null);
}

function fillSelect(id, values, placeholder) {
  const el = qs(id);
  el.innerHTML = "";
  if (placeholder) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    el.appendChild(opt);
  }
  (values || []).forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    el.appendChild(opt);
  });
}

function currentFilters() {
  return {
    q: qs("f-search").value.trim(),
    industry: qs("f-industry").value,
    segment: qs("f-segment").value,
    score_tier: qs("f-tier").value,
    pipeline_stage: qs("f-stage").value,
    meta_ad_count_bucket: qs("f-adbucket").value,
    discount_depth_bucket: qs("f-discount").value,
    audit_completeness: qs("f-audit").value,
    sort: state.sort,
    dir: state.dir,
  };
}

function buildQuery(params) {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v) usp.set(k, v); });
  return usp.toString();
}

async function loadCompanies() {
  const qsStr = buildQuery(currentFilters());
  const res = await fetch("/api/companies?" + qsStr);
  const data = await res.json();
  state.companies = data.companies;
  renderTable();
  qs("result-count").textContent = `${data.count} companies`;
}

["f-search", "f-industry", "f-segment", "f-tier", "f-stage", "f-adbucket", "f-discount", "f-audit"].forEach((id) => {
  qs(id).addEventListener("input", debounce(loadCompanies, 200));
  qs(id).addEventListener("change", loadCompanies);
});

qs("btn-clear-filters").addEventListener("click", () => {
  ["f-search", "f-industry", "f-segment", "f-tier", "f-stage", "f-adbucket", "f-discount", "f-audit"].forEach((id) => {
    qs(id).value = "";
  });
  loadCompanies();
});

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ---------------------------------------------------------------------------
// Table rendering + sorting
// ---------------------------------------------------------------------------

document.querySelectorAll("#companies-table th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (state.sort === key) {
      state.dir = state.dir === "asc" ? "desc" : "asc";
    } else {
      state.sort = key;
      state.dir = "desc";
    }
    document.querySelectorAll("#companies-table th").forEach((h) => h.classList.remove("sorted"));
    th.classList.add("sorted");
    loadCompanies();
  });
});

function renderTable() {
  const tbody = qs("companies-tbody");
  if (!state.companies.length) {
    tbody.innerHTML = `<tr><td colspan="13"><div class="empty-state">No companies match these filters.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = state.companies.map((c) => {
    const noteIcon = c.audit_notes
      ? `<span class="note-icon" title="${esc(c.audit_notes)}">i</span>` : "";
    const companyCell = c.website
      ? `<a href="${esc(c.website)}" target="_blank" rel="noopener"><strong>${esc(c.company_name)}</strong></a><br><a href="${esc(c.website)}" target="_blank" rel="noopener" style="color:#6B7280;font-size:11px;">${esc(c.website)}</a>`
      : `<strong>${esc(c.company_name)}</strong><br><span style="color:#6B7280;font-size:11px;">${esc(c.sub_category || "")}</span>`;
    const dmName = c.decision_maker_name && c.decision_maker_name !== "Unavailable" ? esc(c.decision_maker_name) : "Unavailable";
    const dmRole = c.decision_maker_role ? `<br><span style="color:#6B7280;font-size:11px;">${esc(c.decision_maker_role)}</span>` : "";
    const dmLinkedin = c.decision_maker_linkedin
      ? `<br><a href="${esc(c.decision_maker_linkedin)}" target="_blank" rel="noopener" style="font-size:11px;">LinkedIn &#8599;</a>`
      : "";
    const dmCell = `${dmName}${dmRole}${dmLinkedin}`;
    const stageOptions = (state.meta.pipeline_stages || []).map((s) =>
      `<option value="${esc(s)}" ${s === c.pipeline_stage ? "selected" : ""}>${esc(s)}</option>`
    ).join("");
    const stageSelect = `<select class="stage-select" data-id="${c.id}" style="width:100%;">${stageOptions}</select>`;
    return `
    <tr data-id="${c.id}">
      <td>${companyCell}</td>
      <td>${esc(c.industry)}</td>
      <td>${dmCell}</td>
      <td>${tag(c.meta_ad_count_approx || c.meta_ad_count_bucket)}${noteIcon}</td>
      <td>${freshnessTag(c.creative_freshness_bucket)}</td>
      <td>${discountTag(c.discount_depth_bucket)}</td>
      <td>${convTag(c.conversion_health_bucket)}</td>
      <td>${auditTag(c.audit_completeness)}</td>
      <td class="score-cell">${c.opportunity_score}</td>
      <td>${tierBadge(c.score_tier)}</td>
      <td>${esc(c.segment)}</td>
      <td>${stageSelect}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-sm" data-action="edit" data-id="${c.id}">Edit</button>
          <button class="btn btn-sm btn-primary" data-action="outreach" data-id="${c.id}">Outreach</button>
        </div>
      </td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll('[data-action="edit"]').forEach((b) => b.addEventListener("click", () => openEditModal(b.dataset.id)));
  tbody.querySelectorAll('[data-action="outreach"]').forEach((b) => b.addEventListener("click", () => openOutreachModal(b.dataset.id)));
  tbody.querySelectorAll(".stage-select").forEach((sel) => {
    sel.addEventListener("change", async () => {
      const id = sel.dataset.id;
      const newStage = sel.value;
      sel.disabled = true;
      try {
        await fetch(`/api/companies/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pipeline_stage: newStage }),
        });
        const c = state.companies.find((x) => String(x.id) === String(id));
        if (c) c.pipeline_stage = newStage;
        toast("Stage saved");
      } catch (e) {
        toast("Couldn't save -- try again");
      } finally {
        sel.disabled = false;
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Edit / Add modal
// ---------------------------------------------------------------------------

function openAddModal() {
  state.currentEditId = null;
  qs("edit-modal-title").textContent = "Add company";
  qs("edit-form").reset();
  qs("edit-id").value = "";
  qs("btn-delete-company").style.display = "none";
  qs("modal-edit").classList.add("open");
}

async function openEditModal(id) {
  const res = await fetch(`/api/companies/${id}`);
  const c = await res.json();
  state.currentEditId = id;
  qs("edit-modal-title").textContent = `Edit — ${c.company_name}`;
  qs("edit-id").value = c.id;
  qs("edit-company_name").value = c.company_name || "";
  qs("edit-industry").value = c.industry || "Apparel";
  qs("edit-sub_category").value = c.sub_category || "";
  qs("edit-website").value = c.website || "";
  qs("edit-decision_maker_name").value = c.decision_maker_name || "";
  qs("edit-decision_maker_role").value = c.decision_maker_role || "";
  qs("edit-decision_maker_linkedin").value = c.decision_maker_linkedin || "";
  qs("edit-business_email").value = c.business_email || "";
  qs("edit-business_phone").value = c.business_phone || "";
  qs("edit-pipeline_stage").value = c.pipeline_stage || "N/A";
  qs("edit-segment").value = c.segment || "";
  qs("edit-follow_up_date").value = c.follow_up_date || "";
  qs("edit-notes").value = c.notes || "";
  qs("btn-delete-company").style.display = "inline-block";
  qs("modal-edit").classList.add("open");
}

qs("btn-add").addEventListener("click", openAddModal);

document.querySelectorAll("[data-close-modal]").forEach((el) => {
  el.addEventListener("click", () => {
    document.querySelectorAll(".modal-backdrop").forEach((m) => m.classList.remove("open"));
  });
});

qs("edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    company_name: qs("edit-company_name").value,
    industry: qs("edit-industry").value,
    sub_category: qs("edit-sub_category").value,
    website: qs("edit-website").value,
    decision_maker_name: qs("edit-decision_maker_name").value,
    decision_maker_role: qs("edit-decision_maker_role").value,
    decision_maker_linkedin: qs("edit-decision_maker_linkedin").value,
    business_email: qs("edit-business_email").value,
    business_phone: qs("edit-business_phone").value,
    pipeline_stage: qs("edit-pipeline_stage").value,
    segment: qs("edit-segment").value,
    follow_up_date: qs("edit-follow_up_date").value,
    notes: qs("edit-notes").value,
  };

  if (state.currentEditId) {
    await fetch(`/api/companies/${state.currentEditId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("Saved");
  } else {
    await fetch("/api/companies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("Company added");
  }
  qs("modal-edit").classList.remove("open");
  loadCompanies();
});

qs("btn-delete-company").addEventListener("click", async () => {
  if (!state.currentEditId) return;
  if (!confirm("Delete this company?")) return;
  await fetch(`/api/companies/${state.currentEditId}`, { method: "DELETE" });
  qs("modal-edit").classList.remove("open");
  toast("Deleted");
  loadCompanies();
});

// ---------------------------------------------------------------------------
// Outreach modal
// ---------------------------------------------------------------------------

async function openOutreachModal(id) {
  const res = await fetch(`/api/companies/${id}/outreach`);
  const d = await res.json();
  qs("outreach-title").textContent = `Outreach draft — ${d.company_name}`;
  qs("outreach-research-note").textContent = d.research_note || "No research note captured for this company.";
  const liLink = d.decision_maker_linkedin
    ? `<a href="${esc(d.decision_maker_linkedin)}" target="_blank" rel="noopener">${esc(d.decision_maker_linkedin)}</a>`
    : "Unavailable";
  qs("outreach-contact").innerHTML = `
    <strong>${esc(d.decision_maker_name)}</strong> — ${esc(d.decision_maker_role || "Unavailable")}<br>
    LinkedIn: ${liLink}<br>
    Email: ${esc(d.business_email)}<br>
    Phone: ${esc(d.business_phone)}<br>
    Segment: ${esc(d.segment)}
  `;
  qs("outreach-li-connect-text").textContent = d.linkedin_connect;
  qs("outreach-li-followup-text").textContent = d.linkedin_followup;
  qs("outreach-email-text").textContent = d.email_body;
  qs("outreach-followup-email-text").textContent = d.followup_email_body;
  qs("outreach-subjects").innerHTML = d.email_subject_options.map((s) => `<li>${esc(s)}</li>`).join("");
  qs("modal-outreach").classList.add("open");
}

document.querySelectorAll(".copy-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = qs(btn.dataset.copyTarget);
    navigator.clipboard.writeText(target.textContent).then(() => toast("Copied"));
  });
});

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

qs("btn-export").addEventListener("click", () => {
  const qsStr = buildQuery(currentFilters());
  window.location.href = "/api/export/csv?" + qsStr;
});

// ---------------------------------------------------------------------------
// Pipeline tab
// ---------------------------------------------------------------------------

async function renderPipeline() {
  const res = await fetch("/api/companies?sort=opportunity_score&dir=desc");
  const data = await res.json();
  const stages = state.meta.pipeline_stages;
  const byStage = {};
  stages.forEach((s) => byStage[s] = []);
  data.companies.forEach((c) => {
    if (!byStage[c.pipeline_stage]) byStage[c.pipeline_stage] = [];
    byStage[c.pipeline_stage].push(c);
  });

  const holder = qs("pipeline-columns");
  holder.innerHTML = stages.map((stage) => {
    const items = byStage[stage] || [];
    return `
    <div class="pipeline-col" data-stage="${esc(stage)}">
      <h3>${esc(stage)} <span class="pipeline-count">${items.length}</span></h3>
      <div class="pipeline-col-body" data-stage="${esc(stage)}">
      ${items.map((c) => `
        <div class="pipeline-card" data-id="${c.id}" draggable="true">
          <div class="pname">${esc(c.company_name)}</div>
          <div class="pmeta">${esc(c.industry)} · Tier ${esc(c.score_tier)} · ${c.opportunity_score} pts</div>
        </div>
      `).join("") || `<div class="pipeline-empty" style="color:#9AA0AC;font-size:12px;padding:6px 2px;">No companies</div>`}
      </div>
    </div>`;
  }).join("");

  let draggedId = null;

  holder.querySelectorAll(".pipeline-card").forEach((el) => {
    el.addEventListener("click", () => {
      document.querySelector('.tab-btn[data-tab="table"]').click();
      openEditModal(el.dataset.id);
    });
    el.addEventListener("dragstart", () => {
      draggedId = el.dataset.id;
      el.classList.add("dragging");
    });
    el.addEventListener("dragend", () => {
      el.classList.remove("dragging");
    });
  });

  holder.querySelectorAll(".pipeline-col-body").forEach((col) => {
    col.addEventListener("dragover", (e) => {
      e.preventDefault();
      col.classList.add("drop-target");
    });
    col.addEventListener("dragleave", () => {
      col.classList.remove("drop-target");
    });
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      col.classList.remove("drop-target");
      if (!draggedId) return;
      const newStage = col.dataset.stage;
      await fetch(`/api/companies/${draggedId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pipeline_stage: newStage }),
      });
      toast("Stage saved");
      draggedId = null;
      renderPipeline();
    });
  });
}

// ---------------------------------------------------------------------------
// Segmentation tab
// ---------------------------------------------------------------------------

async function renderSegmentation() {
  const res = await fetch("/api/segments");
  const segments = await res.json();
  qs("segmentation-cards").innerHTML = segments.map((s) => `
    <div class="card">
      <div class="label">Segment</div>
      <h3>${esc(s.name)}</h3>
      <div class="count">${s.company_count}</div>
      <div class="sub">companies${s.avg_opportunity_score !== null ? " · avg score " + s.avg_opportunity_score : ""}</div>
      <p><span class="label">Pain point</span><br>${esc(s.pain_point)}</p>
      <p><span class="label">Pitch angle</span><br>${esc(s.pitch_angle)}</p>
    </div>
  `).join("");
}

// ---------------------------------------------------------------------------
// Scoring tab
// ---------------------------------------------------------------------------

async function renderScoring() {
  const res = await fetch("/api/scoring");
  const data = await res.json();

  document.querySelector("#scoring-framework-table tbody").innerHTML = data.framework.map((f) => `
    <tr><td><strong>${esc(f.name)}</strong></td><td>${f.max_points}</td><td>${esc(f.description)}</td></tr>
  `).join("");

  document.querySelector("#scoring-tiers-table tbody").innerHTML = data.tiers.map((t) => `
    <tr><td>${tierBadge(t.tier)}</td><td>${esc(t.range)}</td><td>${esc(t.meaning)}</td></tr>
  `).join("");

  const tierColors = { A: "#1E8A4C", B: "#2F5DFC", C: "#B4770A", D: "#C13B3B" };
  qs("tier-breakdown").innerHTML = ["A", "B", "C", "D"].map((t) => `
    <div class="tier-chip" style="border-color:${tierColors[t]}33;">
      <div class="n" style="color:${tierColors[t]};">${data.tier_counts[t] || 0}</div>
      <div class="t">Tier ${t} of ${data.total_companies}</div>
    </div>
  `).join("");
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

(async function init() {
  await loadMeta();
  await loadCompanies();
})();
