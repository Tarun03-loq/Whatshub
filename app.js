/* ============================================================
   WhatsHub — Clean App Logic
   WhatsApp Multi-Device Aggregator with Ollama Gemma 2B AI
   Displays: AI Summaries | Priority Queue | Group Chats | Calendar
============================================================ */

"use strict";

const DAEMON = "http://127.0.0.1:5001";

/* ── STATE ── */
const state = {
  tasks: [],
  summaries: [],
  whitelist: [],
  wa: { connected: false, phone: null, qr: null, qr_svg: null, raw_b64: null },
  isLive: false,
  ollama: "unknown",
  currentView: "dashboard",
  calYear: new Date().getFullYear(),
  calMonth: new Date().getMonth(),
  selectedDate: new Date().getDate(),
  daemonTimer: null,
  qrPollTimer: null,
  qrRefreshPending: false,
  wlSearchQuery: "",
};

/* ── SAMPLE DATA (Shown only in offline preview) ── */
const SAMPLE_TASKS = [
  {
    id: "s1", priority: "high", item_type: "submission", category: "college",
    title: "Cloud Computing Lab Record Submission",
    summary: "Mandatory physical submission with professor signatures required. No deadline extensions allowed. Bring your verified record copies.",
    raw_message: "Dear students, the final submission for Cloud Computing Lab Records has been scheduled for tomorrow at 4:00 PM. No extensions will be granted. Bring signed physical copies.",
    group_name: "College CSE Final Year", group_jid: "120363028192847@g.us",
    sender: "Prof. Ramanathan", deadline_display: "Tomorrow at 4:00 PM",
    deadline: new Date(Date.now() + 86400000).toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: "s2", priority: "high", item_type: "meeting", category: "work",
    title: "Hackathon Jury Evaluation Meeting",
    summary: "Mandatory dry-run and jury evaluation meeting with technical evaluators in Audi 3. All team members must join with presentation slides.",
    raw_message: "URGENT: Mandatory technical review meeting tomorrow at 11:30 AM in Audi 3. Join with presentation slides.",
    group_name: "Team Hacknova", group_jid: "120363099991234@g.us",
    sender: "Mentor Dr. Vikram", deadline_display: "Tomorrow 11:30 AM",
    deadline: new Date(Date.now() + 86400000).toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: "s4", priority: "high", item_type: "duedate", category: "money",
    title: "Electricity Bill Payment Due Today",
    summary: "Monthly TNEB bill of ₹1,847 due today. Please pay online via TNEB portal or any UPI app to avoid ₹200 late penalty.",
    raw_message: "Attention: TNEB Electricity bill of ₹1,847 is due today. Please pay online via TNEB portal or any UPI app to avoid ₹200 late penalty.",
    group_name: "Apartment Residents", group_jid: "120363011122334@g.us",
    sender: "Secretary Ravi", deadline_display: "Today by 6:00 PM",
    deadline: new Date().toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: "s3", priority: "medium", item_type: "assignment", category: "college",
    title: "Data Structures Assignment #4",
    summary: "Assignment on graph traversal algorithms due this Friday. Upload on the student portal before 11:59 PM.",
    raw_message: "DS Assignment 4 on Graph algorithms is due this Friday. Upload on the student portal before 11:59 PM.",
    group_name: "College CSE Final Year", group_jid: "120363028192847@g.us",
    sender: "Dr. Senthil", deadline_display: "Friday at 11:59 PM",
    deadline: new Date(Date.now() + 5 * 86400000).toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: "s5", priority: "medium", item_type: "cultural", category: "college",
    title: "Annual Fest Band Auditions",
    summary: "Annual cultural fest band auditions this Saturday at 2:00 PM in College Auditorium. Register your group by Thursday midnight on the fest portal.",
    raw_message: "Annual Fest band auditions on Saturday 2 PM at College Auditorium. Register your group by Thursday midnight on the fest portal.",
    group_name: "College CSE Final Year", group_jid: "120363028192847@g.us",
    sender: "Fest Committee", deadline_display: "Saturday at 2:00 PM",
    deadline: new Date(Date.now() + 6 * 86400000).toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: "s6", priority: "low", item_type: "assignment", category: "work",
    title: "API Documentation Review PR",
    summary: "Review and merge the API docs PR before the end of the sprint. Low urgency.",
    raw_message: "Team please review the API documentation PR #247 before end of sprint. It's the docs update for the new auth endpoints.",
    group_name: "Team Hacknova", group_jid: "120363099991234@g.us",
    sender: "Tarun S (Lead)", deadline_display: "End of sprint",
    deadline: null,
    created_at: new Date().toISOString()
  },
];

const SAMPLE_SUMMARIES = [
  {
    group_jid: "120363028192847@g.us", group_name: "College CSE Final Year",
    summary: "Lab record submission deadline tomorrow at 4:00 PM (mandatory physical copies). DS Assignment #4 due Friday on student portal. Annual fest band auditions Saturday — register by Thursday.",
    message_count: 12, last_updated: new Date(Date.now() - 3 * 60000).toISOString(),
    ai_model: "Gemma 2B (Ollama)"
  },
  {
    group_jid: "120363099991234@g.us", group_name: "Team Hacknova",
    summary: "Mandatory jury evaluation meeting tomorrow at 11:30 AM in Audi 3 — all members rehearse slides. API documentation PR #247 review needed before sprint end.",
    message_count: 7, last_updated: new Date(Date.now() - 12 * 60000).toISOString(),
    ai_model: "Gemma 2B (Ollama)"
  },
  {
    group_jid: "120363011122334@g.us", group_name: "Apartment Residents",
    summary: "TNEB electricity bill ₹1,847 due today by 6:00 PM — pay via UPI to avoid penalty. Maintenance work scheduled next week Monday 9–11 AM.",
    message_count: 4, last_updated: new Date(Date.now() - 25 * 60000).toISOString(),
    ai_model: "Gemma 2B (Ollama)"
  },
  {
    group_jid: "120363088877665@g.us", group_name: "Family Group",
    summary: "Family dinner at Uncle Rajan's this Sunday 7:00 PM. Bring medicines. Birthday greetings and return pickup reminders shared.",
    message_count: 9, last_updated: new Date(Date.now() - 60 * 60000).toISOString(),
    ai_model: "Gemma 2B (Ollama)"
  },
];

/* ── HELPERS ── */
function toast(msg, icon = "✅", dur = 3000) {
  const t = document.getElementById("toast");
  const ti = document.getElementById("toast-icon");
  const tm = document.getElementById("toast-msg");
  if (!t || !ti || !tm) return;
  ti.textContent = icon;
  tm.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), dur);
}

function relTime(iso) {
  if (!iso) return "recently";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return m + "m ago";
  const h = Math.floor(m / 60);
  if (h < 24) return h + "h ago";
  return Math.floor(h / 24) + "d ago";
}

function priorityColor(p) {
  if (p === "high") return "#f87171";
  if (p === "medium") return "#fbbf24";
  return "var(--wa-green)";
}

function escHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ── TIME PARSING & ORDERING UTILITY ── */
function extractEventTimeInfo(task) {
  let minutes = 1439; // default end of day
  let timeStr = "TBD";

  // 1. Try deadline ISO
  if (task.deadline) {
    const d = new Date(task.deadline);
    if (!isNaN(d.getTime())) {
      const h = d.getHours();
      const m = d.getMinutes();
      if (h !== 0 || m !== 0) {
        minutes = h * 60 + m;
        const ampm = h >= 12 ? "PM" : "AM";
        const h12 = h % 12 || 12;
        timeStr = `${h12}:${m < 10 ? "0" + m : m} ${ampm}`;
      }
    }
  }

  // 2. Parse from deadline_display if TBD or default
  if (timeStr === "TBD" && task.deadline_display) {
    const match = task.deadline_display.match(/(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)?/i);
    if (match) {
      let h = parseInt(match[1]);
      const m = match[2] ? parseInt(match[2]) : 0;
      const ampm = match[3] ? match[3].toUpperCase() : null;
      if (ampm === "PM" && h < 12) h += 12;
      if (ampm === "AM" && h === 12) h = 0;
      minutes = h * 60 + m;
      const dispAmpm = h >= 12 ? "PM" : "AM";
      const h12 = h % 12 || 12;
      timeStr = `${h12}:${m < 10 ? "0" + m : m} ${dispAmpm}`;
    } else {
      timeStr = task.deadline_display;
    }
  }

  return { minutes, timeStr };
}

/* ── MODAL SYSTEM ── */
function openModal(id) { document.getElementById(id)?.classList.add("active"); }
function closeModal(id) { document.getElementById(id)?.classList.remove("active"); }

document.addEventListener("click", e => {
  const btn = e.target.closest("[data-close]");
  if (btn) closeModal(btn.dataset.close);
  const overlay = e.target;
  if (overlay.classList.contains("modal-overlay")) closeModal(overlay.id);
});

/* ── NAVIGATION ── */
function setView(view) {
  state.currentView = view;
  ["dashboard", "priority", "calendar"].forEach(v => {
    const el = document.getElementById("view-" + v);
    if (el) el.style.display = "none";
  });
  const cur = document.getElementById("view-" + view);
  if (cur) cur.style.display = "grid";

  document.querySelectorAll(".tab-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  const titles = { dashboard: "Dashboard", priority: "Priority Queue", calendar: "Event Calendar" };
  const vTitle = document.getElementById("view-title");
  if (vTitle) vTitle.textContent = titles[view] || view;

  if (view === "calendar") renderCalendar();
}

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});

document.getElementById("nav-home")?.addEventListener("click", () => {
  setView("dashboard");
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("nav-home").classList.add("active");
});
document.getElementById("nav-chats")?.addEventListener("click", () => {
  setView("dashboard");
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("nav-chats").classList.add("active");
});
document.getElementById("nav-calendar-btn")?.addEventListener("click", () => {
  setView("calendar");
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("nav-calendar-btn").classList.add("active");
});
document.getElementById("nav-whitelist-btn")?.addEventListener("click", () => {
  openModal("modal-whitelist");
  fetchWhitelistGroups();
});
document.getElementById("btn-simulate")?.addEventListener("click", () => openModal("modal-simulate"));
document.getElementById("btn-refresh-all")?.addEventListener("click", () => {
  refreshAll();
  toast("Refreshing live dashboard data...", "🔄");
});

/* ── DAEMON MONITOR ── */
async function checkDaemonStatus() {
  try {
    const r = await fetch(DAEMON + "/status", { signal: AbortSignal.timeout(2500) });
    if (!r.ok) return;
    const d = await r.json();
    state.wa = { ...state.wa, ...d };

    const dot = document.getElementById("wa-dot");
    const txt = document.getElementById("wa-status-text");

    if (d.connected) {
      if (dot) dot.className = "dot online";
      if (txt) txt.textContent = d.phone ? `+${d.phone}` : "Connected";

      if (!state.isLive) {
        state.isLive = true;
        state.tasks = [];
        state.summaries = [];
        toast("WhatsApp connected! Real data loaded.", "🟢", 3500);
        await refreshAll();
      }
    } else {
      if (dot) dot.className = "dot";
      if (txt) txt.textContent = "Link WhatsApp";
      state.wa.connected = false;
    }
  } catch (_) {}
}

/* ── QR CODE GENERATION & POLLING ── */
async function requestFreshQR() {
  if (state.qrRefreshPending) return;
  state.qrRefreshPending = true;
  const badge = document.getElementById("qr-source-badge");
  const display = document.getElementById("qrcode-display");
  if (badge) badge.textContent = "🔄 Handshaking with WhatsApp Web...";
  if (display) {
    display.innerHTML = `<div style="color:var(--text-muted);font-size:12px;padding:30px;text-align:center;">
      <div style="font-size:24px;margin-bottom:8px;">⏳</div>
      Connecting to WhatsApp Web...<br><span style="font-size:11px;color:var(--wa-green);">Generating live pairing QR...</span>
    </div>`;
  }
  try {
    const response = await fetch(DAEMON + "/refresh_qr", { method: "POST" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  } catch (_) {}
  setTimeout(() => { state.qrRefreshPending = false; }, 5000);
  setTimeout(pollQR, 1000);
}

async function pollQR() {
  const display = document.getElementById("qrcode-display");
  const caption = document.getElementById("qr-caption");
  const badge = document.getElementById("qr-source-badge");
  const b64txt = document.getElementById("qr-base64-text");

  try {
    const r = await fetch(DAEMON + "/status", { signal: AbortSignal.timeout(2500) });
    if (!r.ok) throw new Error("Bad response");
    const d = await r.json();

    if (d.connected) {
      const wasDisconnected = !state.wa.connected;
      state.wa.connected = true;
      state.isLive = true;
      state.wa.phone = d.phone;

      document.getElementById("qr-view").style.display = "none";
      document.getElementById("connected-view").style.display = "block";
      document.getElementById("connected-phone").textContent =
        d.phone ? `Phone: +${d.phone}` : "Active Session";
      if (badge) badge.textContent = "🟢 Connected";
      if (state.qrPollTimer) { clearInterval(state.qrPollTimer); state.qrPollTimer = null; }

      const dot = document.getElementById("wa-dot");
      const txt = document.getElementById("wa-status-text");
      if (dot) dot.className = "dot online";
      if (txt) txt.textContent = d.phone ? `+${d.phone}` : "Connected";

      // Purge sample data on connection
      if (wasDisconnected) {
        state.tasks = [];
        state.summaries = [];
        toast("WhatsApp connected! Demo data cleared. Loading live chats...", "🎉", 4000);
        await refreshAll();
      }
      return;
    }

    state.wa.connected = false;

    if (d.qr_svg || d.qr) {
      const qrSource = d.qr_svg || d.qr;
      if (display) {
        display.innerHTML = `<img src="${qrSource}" alt="WhatsApp Pairing QR" style="width:250px;height:250px;object-fit:contain;display:block;">`;
      }
      if (caption) {
        caption.textContent = "Scan from WhatsApp › Linked Devices › Link a Device";
        caption.style.color = "var(--wa-green)";
      }
      const exp = d.expires_in !== undefined ? d.expires_in : 25;
      if (badge) badge.textContent = `🟢 Live QR · Refreshes in ${exp}s`;
      if (b64txt && d.raw_b64) b64txt.textContent = d.raw_b64.substring(0, 80) + "...";

      if (exp <= 0) {
        requestFreshQR();
      }
    } else {
      if (display) {
        display.innerHTML = `<div style="color:var(--text-muted);font-size:12px;padding:30px;text-align:center;">
          <div style="font-size:24px;margin-bottom:8px;">⏳</div>
          Connecting to WhatsApp Web...<br><span style="font-size:11px;color:var(--wa-green);">Handshaking...</span>
        </div>`;
      }
      if (caption) {
        caption.textContent = "Connecting to WhatsApp Web...";
        caption.style.color = "var(--orange, #f59e0b)";
      }
      if (badge) badge.textContent = "🟡 Connecting to WhatsApp Web...";
    }
  } catch (_) {
    const hostedPreview = location.protocol === "https:" && !["localhost", "127.0.0.1"].includes(location.hostname);
    const startHint = hostedPreview
      ? "Run start_whatshub.bat on this computer to use live WhatsApp data."
      : "python backend/listener.py";
    if (display) {
      display.innerHTML = `<div style="color:#f87171;font-size:12px;padding:30px;text-align:center;">
        <div style="font-size:24px;margin-bottom:8px;">⚠️</div>
        Daemon Offline<br><br><code style="background:rgba(255,255,255,0.06);padding:4px 8px;border-radius:4px;font-size:11px;">${escHtml(startHint)}</code>
      </div>`;
    }
    if (caption) {
      caption.textContent = startHint;
      caption.style.color = "#f87171";
    }
    if (badge) badge.textContent = "⛔ Daemon not running on :5001";
  }
}

function openModalWhatsApp() {
  openModal("modal-whatsapp");
  if (state.wa.connected) {
    document.getElementById("qr-view").style.display = "none";
    document.getElementById("connected-view").style.display = "block";
  } else {
    document.getElementById("qr-view").style.display = "block";
    document.getElementById("connected-view").style.display = "none";
    pollQR();
    if (state.qrPollTimer) clearInterval(state.qrPollTimer);
    state.qrPollTimer = setInterval(() => {
      if (document.getElementById("modal-whatsapp").classList.contains("active")) {
        pollQR();
      } else {
        clearInterval(state.qrPollTimer);
        state.qrPollTimer = null;
      }
    }, 1500);
  }
}

document.getElementById("btn-link-whatsapp")?.addEventListener("click", openModalWhatsApp);
document.getElementById("btn-refresh-neonize-qr")?.addEventListener("click", () => {
  requestFreshQR();
  toast("Requesting fresh pairing QR...", "🔄");
});

document.getElementById("btn-disconnect")?.addEventListener("click", async () => {
  try { 
    await fetch(DAEMON + "/disconnect", { method: "POST" }); 
  } catch (_) {}
  state.wa = { connected: false, phone: null, qr: null, qr_svg: null, raw_b64: null };
  state.isLive = false;
  document.getElementById("qr-view").style.display = "block";
  document.getElementById("connected-view").style.display = "none";
  const dot = document.getElementById("wa-dot");
  const txt = document.getElementById("wa-status-text");
  if (dot) dot.className = "dot";
  if (txt) txt.textContent = "Link WhatsApp";
  
  // Completely clear old messages and summaries from the dashboard
  state.tasks = [];
  state.summaries = [];
  renderAll();
  toast("WhatsApp disconnected. All dashboard messages cleared.", "🔴");
  // Immediately request a fresh pairing QR for next connection
  requestFreshQR();
});

/* ── AI ENGINE STATUS CHECK ── */
async function checkOllama() {
  const chip = document.getElementById("ollama-chip");
  if (!chip) return;
  try {
    const r = await fetch("http://localhost:11434", { signal: AbortSignal.timeout(2000) });
    state.ollama = "online";
    chip.className = "ai-engine-chip";
    chip.innerHTML = `<div class="dot"></div>AI Engine · Online`;
  } catch (_) {
    state.ollama = "offline";
    chip.className = "ai-engine-chip offline";
    chip.innerHTML = `<div class="dot"></div>AI Engine · Standby`;
  }
}

/* ── GROUP JID WHITELIST MANAGEMENT (WhatsApp discovery & selection) ── */
async function fetchWhitelistGroups() {
  const pill = document.getElementById("wl-status-pill");
  try {
    const r = await fetch(DAEMON + "/groups", { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      const d = await r.json();
      if (d.groups && d.groups.length > 0) {
        state.whitelist = d.groups;
        if (pill) {
          pill.textContent = d.connected
            ? `🟢 Linked WhatsApp · ${d.groups.length} groups discovered`
            : `🟡 Standby Mode · ${d.groups.length} configured groups`;
        }
        renderWhitelist();
        renderGroupsPanel();
        return;
      }
    }
  } catch (_) {}

  // Fallback initial groups if daemon offline
  if (state.whitelist.length === 0) {
    state.whitelist = [
      { jid: "120363028192847@g.us", name: "College CSE Final Year", icon: "🎓", is_active: true, is_whatsapp: false },
      { jid: "120363099991234@g.us", name: "Team Hacknova", icon: "🤝", is_active: true, is_whatsapp: false },
      { jid: "120363011122334@g.us", name: "Apartment Residents", icon: "🏠", is_active: true, is_whatsapp: false },
      { jid: "120363088877665@g.us", name: "Family Group", icon: "👨‍👩‍👧", is_active: true, is_whatsapp: false },
    ];
  }
  renderWhitelist();
  renderGroupsPanel();
}

function renderWhitelist() {
  const list = document.getElementById("wl-groups-list");
  if (!list) return;

  const q = (state.wlSearchQuery || "").toLowerCase();
  const filtered = state.whitelist.filter(g =>
    (g.name || "").toLowerCase().includes(q) || (g.jid || "").toLowerCase().includes(q)
  );

  if (filtered.length === 0) {
    list.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:12px;">
      No groups matched "${escHtml(q)}".<br>Sync from WhatsApp or add a custom JID below.
    </div>`;
    return;
  }

  list.innerHTML = filtered.map(g => `
    <div class="wl-group-item ${g.is_active ? 'active' : ''}">
      <div class="wl-group-info">
        <div class="wl-group-avatar">${escHtml(g.icon || '👥')}</div>
        <div class="wl-group-text">
          <div class="wl-group-name">
            ${escHtml(g.name)}
            ${g.is_whatsapp ? '<span class="wl-tag-wa">WhatsApp</span>' : ''}
          </div>
          <div class="wl-group-jid">${escHtml(g.jid)}</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-size:10px;font-weight:700;color:${g.is_active ? 'var(--wa-green)' : 'var(--text-subtle)'};">
          ${g.is_active ? 'TRACKED' : 'IGNORED'}
        </span>
        <button class="wl-toggle-switch ${g.is_active ? 'on' : ''}" data-jid="${escHtml(g.jid)}" title="Toggle Ollama AI Tracking"></button>
        <button class="btn btn-danger" style="padding:3px 7px;font-size:10px;border-radius:4px;" data-remove-jid="${escHtml(g.jid)}" title="Remove Group">✕</button>
      </div>
    </div>
  `).join("");

  // Attach toggle listeners
  list.querySelectorAll(".wl-toggle-switch").forEach(btn => {
    btn.addEventListener("click", async () => {
      const jid = btn.dataset.jid;
      const grp = state.whitelist.find(g => g.jid === jid);
      if (!grp) return;
      const previous = grp.is_active;
      grp.is_active = !grp.is_active;

      // Update UI switch immediately
      renderWhitelist();
      renderGroupsPanel();

      // Post to backend
      try {
        const response = await fetch(DAEMON + "/groups/toggle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ jid, is_active: grp.is_active })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        if (!result.success) throw new Error(result.error || "Update rejected");
      } catch (err) {
        grp.is_active = previous;
        renderWhitelist();
        renderGroupsPanel();
        toast("Could not update group. Is the local daemon running?", "⚠️");
        return;
      }

      // Re-summarize active groups with Ollama
      await fetchSummaries();
      renderSummariesPanel();
      toast(`Group '${grp.name}' ${grp.is_active ? "enabled for Ollama AI" : "ignored"}`, grp.is_active ? "🟢" : "⚪");
    });
  });

  // Attach remove listeners
  list.querySelectorAll("[data-remove-jid]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const jid = btn.dataset.removeJid;
      const previousGroups = [...state.whitelist];
      state.whitelist = state.whitelist.filter(g => g.jid !== jid);
      renderWhitelist();
      renderGroupsPanel();
      try {
        const response = await fetch(DAEMON + "/groups/remove", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ jid })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        if (!result.success) throw new Error(result.error || "Removal rejected");
      } catch (_) {
        state.whitelist = previousGroups;
        renderWhitelist();
        renderGroupsPanel();
        toast("Could not remove group. Is the local daemon running?", "⚠️");
        return;
      }
      toast("Group removed from whitelist", "🗑️");
    });
  });
}

document.getElementById("wl-search")?.addEventListener("input", e => {
  state.wlSearchQuery = e.target.value.trim();
  renderWhitelist();
});

document.getElementById("btn-sync-groups")?.addEventListener("click", async () => {
  const btn = document.getElementById("btn-sync-groups");
  btn.classList.add("spinning");
  await fetchWhitelistGroups();
  btn.classList.remove("spinning");
  toast("WhatsApp groups synced!", "🔄");
});

document.getElementById("btn-add-wl")?.addEventListener("click", async () => {
  const nameInput = document.getElementById("wl-name");
  const jidInput = document.getElementById("wl-jid");
  const name = nameInput.value.trim();
  const jid = jidInput.value.trim();
  if (!jid) { toast("Enter group JID (e.g. 120363@g.us)", "⚠️"); return; }

  const groupName = name || `Group ${jid.split('@')[0]}`;
  state.whitelist.push({ jid, name: groupName, icon: "💬", is_active: true, is_whatsapp: false });
  nameInput.value = "";
  jidInput.value = "";
  renderWhitelist();
  renderGroupsPanel();

  try {
    const response = await fetch(DAEMON + "/groups/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jid, name: groupName, icon: "💬" })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (!result.success) throw new Error(result.error || "Add rejected");
  } catch (_) {
    state.whitelist = state.whitelist.filter(g => g.jid !== jid);
    renderWhitelist();
    renderGroupsPanel();
    toast("Could not save group. Is the local daemon running?", "⚠️");
    return;
  }
  toast("Group added to whitelist", "✅");
});

/* ── FETCH REAL TASKS FROM DAEMON (Priority Sorted) ── */
async function fetchTasks() {
  try {
    const r = await fetch(DAEMON + "/tasks", { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      const d = await r.json();
      if (d.tasks && d.tasks.length > 0) {
        state.tasks = d.tasks;
        state.isLive = true;
        return;
      } else if (state.isLive || state.wa.connected) {
        state.tasks = [];
        return;
      }
    }
  } catch (_) {}

  if (!state.isLive && !state.wa.connected) {
    state.tasks = SAMPLE_TASKS;
  } else {
    state.tasks = [];
  }
}

/* ── FETCH REAL SUMMARIES FROM OLLAMA AI ── */
async function fetchSummaries() {
  try {
    const r = await fetch(DAEMON + "/summarize", { signal: AbortSignal.timeout(12000) });
    if (r.ok) {
      const d = await r.json();
      if (d.summaries && d.summaries.length > 0) {
        state.summaries = d.summaries;
        if (d.ollama_status) state.ollama = d.ollama_status;
        state.isLive = true;
        return;
      } else if (state.isLive || state.wa.connected) {
        state.summaries = [];
        if (d.ollama_status) state.ollama = d.ollama_status;
        return;
      }
    }
  } catch (_) {}

  if (!state.isLive && !state.wa.connected) {
    state.summaries = SAMPLE_SUMMARIES;
  } else {
    state.summaries = [];
  }
}

/* ── TRIGGER AI RE-SUMMARIZATION ── */
document.getElementById("btn-summarize-now")?.addEventListener("click", async () => {
  const btn = document.getElementById("btn-summarize-now");
  btn.textContent = "⏳ Thinking...";
  btn.disabled = true;
  toast("Running AI summarization...", "🧠");
  await fetchSummaries();
  renderSummariesPanel();
  renderStats();
  btn.textContent = "🧠 Run AI";
  btn.disabled = false;
  toast("Summaries updated!", "✨");
});

/* ── RENDER STATS ── */
function renderStats() {
  const urgent = state.tasks.filter(t => t.priority === "high").length;
  const groups = new Set(state.summaries.map(s => s.group_jid)).size;
  const msgCount = state.summaries.reduce((a, s) => a + (s.message_count || 0), 0);

  const elMsg = document.getElementById("stat-messages");
  const elUrg = document.getElementById("stat-urgent");
  const elTsk = document.getElementById("stat-tasks");
  const elGrp = document.getElementById("stat-groups");

  if (elMsg) elMsg.textContent = state.isLive ? msgCount : (msgCount || 32);
  if (elUrg) elUrg.textContent = urgent;
  if (elTsk) elTsk.textContent = state.tasks.length;
  if (elGrp) elGrp.textContent = state.isLive ? Math.max(groups, state.whitelist.filter(g => g.is_active).length) : state.whitelist.length;
}

/* ── RENDER AI SUMMARIES SPACE ── */
function renderSummariesPanel() {
  const panel = document.getElementById("summaries-panel");
  const count = document.getElementById("summary-count");
  if (!panel || !count) return;

  if (!state.summaries.length) {
    if (state.wa.connected || state.isLive) {
      panel.innerHTML = `<div class="empty-state" style="padding:40px 20px;text-align:center;">
        <div class="empty-icon" style="font-size:36px;margin-bottom:10px;">🟢</div>
        <div class="empty-title" style="font-size:15px;font-weight:700;color:var(--wa-green);margin-bottom:6px;">WhatsApp Connected · Listening</div>
        <div class="empty-sub" style="font-size:12px;color:var(--text-muted);max-width:300px;margin:0 auto;line-height:1.5;">
          Demo data cleared. Incoming messages from your active groups will be summarized here by AI.
        </div>
      </div>`;
    } else {
      panel.innerHTML = `<div class="empty-state">
        <div class="empty-icon">🧠</div>
        <div class="empty-title">No summaries yet</div>
        <div class="empty-sub">Simulate a message or connect WhatsApp to see AI summaries here.</div>
      </div>`;
    }
    count.textContent = "0 groups";
    return;
  }

  count.textContent = state.summaries.length + " groups";
  panel.innerHTML = state.summaries.map((s, idx) => {
    const prioColor = s.priority === "high" ? "#f87171" : s.priority === "medium" ? "#fbbf24" : "var(--wa-green)";
    const prioLabel = (s.priority || "low").toUpperCase();
    const topicCount = (s.topics && s.topics.length) ? s.topics.length : 1;
    return `
    <div class="summary-card interactive-group-card" data-summary-idx="${idx}" style="border-left: 3px solid ${prioColor}; cursor: pointer; transition: transform 0.15s, background 0.15s;" title="Tap to explore categorized topics">
      <div class="summary-card-header">
        <div class="summary-group-name">
          <span class="group-dot" style="background:${prioColor};"></span>
          ${escHtml(s.group_name)}
          <span style="font-size:10px;font-weight:700;color:${prioColor};background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;margin-left:6px;">${prioLabel}</span>
          <span style="font-size:10px;color:var(--text-muted);background:rgba(255,255,255,0.04);padding:2px 6px;border-radius:4px;margin-left:4px;">${topicCount} topic${topicCount !== 1 ? 's' : ''}</span>
        </div>
        <span class="summary-msg-count">${s.message_count} msg${s.message_count !== 1 ? "s" : ""}</span>
      </div>
      <div class="summary-text" style="white-space:pre-line;">${escHtml(s.summary)}</div>
      <div class="summary-footer" style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
        <span class="summary-time">${relTime(s.last_updated)}</span>
        <span style="font-size:11px;color:var(--wa-green);font-weight:600;">Tap to view topics ➔</span>
      </div>
    </div>
  `;
  }).join("");

  // Attach click listener to each summary card to open the group topics modal
  panel.querySelectorAll(".interactive-group-card").forEach(card => {
    card.addEventListener("click", () => {
      const idx = parseInt(card.dataset.summaryIdx, 10);
      const groupData = state.summaries[idx];
      if (groupData) {
        openGroupTopicsModal(groupData);
      }
    });
  });
}

let currentActiveGroupData = null;

/* ── MODAL 1: GROUP TOPICS BREAKDOWN ── */
function openGroupTopicsModal(group) {
  currentActiveGroupData = group;
  const titleEl = document.getElementById("group-topics-title");
  const subEl = document.getElementById("group-topics-subtitle");
  const overviewEl = document.getElementById("group-topics-overview");
  const listEl = document.getElementById("group-topics-list");

  if (titleEl) titleEl.textContent = group.group_name || "Group Topics";
  if (subEl) subEl.textContent = `${group.message_count} messages · Priority: ${(group.priority || "low").toUpperCase()}`;
  if (overviewEl) overviewEl.textContent = group.summary || "Conversation categorized into topics below:";

  const topics = group.topics || [];
  if (listEl) {
    if (!topics.length) {
      listEl.innerHTML = `<div style="text-align:center;padding:16px;color:var(--text-muted);">No separate topics found.</div>`;
    } else {
      listEl.innerHTML = topics.map((top, tIdx) => {
        const topColor = top.priority === "high" ? "#f87171" : top.priority === "medium" ? "#fbbf24" : "var(--wa-green)";
        return `
          <div class="topic-row-card" data-topic-idx="${tIdx}" style="background:var(--bg-card);border:1px solid var(--border);border-left:3px solid ${topColor};border-radius:8px;padding:12px 14px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;transition:background 0.15s;" onmouseover="this.style.background='var(--bg-input)'" onmouseout="this.style.background='var(--bg-card)'">
            <div style="flex:1;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                <span style="font-size:10px;font-weight:700;color:${topColor};background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;">${(top.priority || "low").toUpperCase()}</span>
                <span style="font-weight:600;font-size:13px;color:var(--text);">${escHtml(top.name)}</span>
              </div>
              <div style="font-size:11.5px;color:var(--text-muted);">
                ${top.items_count} message${top.items_count !== 1 ? 's' : ''} ${top.deadlines && top.deadlines.length ? '· ⏰ ' + escHtml(top.deadlines.join(', ')) : ''}
              </div>
            </div>
            <div style="font-size:12px;color:var(--wa-green);font-weight:600;margin-left:12px;">
              Details ➔
            </div>
          </div>
        `;
      }).join("");

      listEl.querySelectorAll(".topic-row-card").forEach(el => {
        el.addEventListener("click", () => {
          const tIdx = parseInt(el.dataset.topicIdx, 10);
          const selectedTopic = topics[tIdx];
          if (selectedTopic) {
            openTopicDetailModal(group, selectedTopic);
          }
        });
      });
    }
  }

  openModal("modal-group-topics");
}

/* ── MODAL 2: ELABORATE TOPIC DETAILS ── */
function openTopicDetailModal(group, topic) {
  const titleEl = document.getElementById("topic-detail-title");
  const groupEl = document.getElementById("topic-detail-group");
  const summaryEl = document.getElementById("topic-detail-summary");
  const messagesEl = document.getElementById("topic-detail-messages");

  if (titleEl) titleEl.textContent = topic.name;
  if (groupEl) groupEl.textContent = `${group.group_name} · Priority: ${(topic.priority || "low").toUpperCase()} · ${topic.items_count} messages`;
  if (summaryEl) summaryEl.textContent = topic.elaborate_summary || "No elaborate summary available.";

  if (messagesEl) {
    const msgs = topic.recent_messages || [];
    if (!msgs.length) {
      messagesEl.innerHTML = `<div style="text-align:center;padding:12px;color:var(--text-muted);font-size:12px;">No individual message records.</div>`;
    } else {
      messagesEl.innerHTML = msgs.map(m => `
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:8px 10px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:3px;font-size:10.5px;color:var(--text-muted);">
            <span style="font-weight:600;color:var(--wa-green);">${escHtml(m.sender || "Sender")}</span>
            <span>${relTime(m.created_at)}</span>
          </div>
          <div style="font-size:12px;color:var(--text);line-height:1.4;">${escHtml(m.text)}</div>
        </div>
      `).join("");
    }
  }

  closeModal("modal-group-topics");
  openModal("modal-topic-detail");
}

// Back button handler from Topic Details back to Group Topics
document.getElementById("btn-back-to-group-topics")?.addEventListener("click", () => {
  closeModal("modal-topic-detail");
  if (currentActiveGroupData) {
    openGroupTopicsModal(currentActiveGroupData);
  }
});

/* ── RENDER PRIORITY QUEUE SPACE (Strict Priority Order: High -> Medium -> Low) ── */
function renderPriorityPanel() {
  const panel = document.getElementById("priority-panel");
  const count = document.getElementById("priority-count");
  if (!panel || !count) return;

  if (!state.tasks.length) {
    if (state.wa.connected || state.isLive) {
      panel.innerHTML = `<div class="empty-state" style="padding:40px 20px;text-align:center;">
        <div class="empty-icon" style="font-size:36px;margin-bottom:10px;">⚡</div>
        <div class="empty-title" style="font-size:15px;font-weight:700;color:var(--text-primary);margin-bottom:6px;">Live Priority Queue Active</div>
        <div class="empty-sub" style="font-size:12px;color:var(--text-muted);max-width:300px;margin:0 auto;line-height:1.5;">
          Demo data cleared. Any action items, deadlines, or submissions in your chats will be prioritized here in real-time.
        </div>
      </div>`;
    } else {
      panel.innerHTML = `<div class="empty-state">
        <div class="empty-icon">⚡</div>
        <div class="empty-title">No tasks yet</div>
        <div class="empty-sub">Simulate a WhatsApp message to see priority-sorted action items.</div>
      </div>`;
    }
    count.textContent = "0 items";
    return;
  }

  // Strict Priority Order: High (0), Medium (1), Low (2)
  const sorted = [...state.tasks].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return (order[a.priority] ?? 3) - (order[b.priority] ?? 3);
  });

  count.textContent = sorted.length + " items";
  panel.innerHTML = sorted.map(t => taskCard(t)).join("");

  panel.querySelectorAll(".task-card").forEach((el, i) => {
    el.addEventListener("click", () => openTaskModal(sorted[i]));
  });
}

/* ── RENDER GROUPS PANEL ── */
function renderGroupsPanel() {
  const panel = document.getElementById("groups-panel");
  const count = document.getElementById("groups-count");
  if (!panel || !count) return;

  const groups = state.whitelist.filter(g => g.is_active);
  count.textContent = groups.length;

  if (!groups.length) {
    panel.innerHTML = `<div class="empty-state">
      <div class="empty-icon">💬</div>
      <div class="empty-title">No groups selected</div>
      <div class="empty-sub">Click 'Whitelist' to select groups to track.</div>
    </div>`;
    return;
  }

  panel.innerHTML = groups.map(g => {
    const gTasks = state.tasks.filter(t => t.group_jid === g.jid);
    const preview = gTasks.length ? gTasks[0].title : (state.wa.connected ? "Active & Monitoring" : "Standby");
    const badge = gTasks.length;
    return `<div class="chat-item" data-jid="${escHtml(g.jid)}">
      <div class="chat-avatar">${escHtml(g.icon || '👥')}</div>
      <div class="chat-info">
        <div class="chat-name">${escHtml(g.name)}</div>
        <div class="chat-preview">${escHtml(preview)}</div>
      </div>
      <div class="chat-meta">
        <div class="chat-time">${state.wa.connected ? "Live" : "Standby"}</div>
        ${badge ? `<div class="chat-badge">${badge}</div>` : ""}
      </div>
    </div>`;
  }).join("");
}

/* ── RENDER PRIORITY VIEW (3 Columns: High / Medium / Low) ── */
function renderPriorityView() {
  const levels = ["high", "medium", "low"];
  const ids = ["panel-high", "panel-medium", "panel-low"];
  const counts = ["ph-count", "pm-count", "pl-count"];

  levels.forEach((lvl, i) => {
    const items = state.tasks.filter(t => t.priority === lvl);
    const cEl = document.getElementById(counts[i]);
    const panel = document.getElementById(ids[i]);
    if (cEl) cEl.textContent = items.length;
    if (!panel) return;

    if (!items.length) {
      panel.innerHTML = `<div class="empty-state"><div class="empty-icon">✅</div><div class="empty-title">Nothing here</div></div>`;
      return;
    }
    panel.innerHTML = items.map(t => taskCard(t)).join("");
    panel.querySelectorAll(".task-card").forEach((el, j) => {
      el.addEventListener("click", () => openTaskModal(items[j]));
    });
  });
}

/* ── TASK CARD HTML ── */
function taskCard(t) {
  const priority = ["high", "medium", "low"].includes(t.priority) ? t.priority : "low";
  const pLabel = priority === "high" ? "🔴 High" : priority === "medium" ? "🟡 Medium" : "🟢 Low";
  return `<div class="task-card">
    <div class="task-card-top">
      <div class="task-title">${escHtml(t.title)}</div>
      <span class="task-priority-badge ${priority}">${pLabel}</span>
    </div>
    <div class="task-summary">${escHtml((t.summary || "").substring(0, 100))}...</div>
    <div class="task-meta">
      ${t.deadline_display ? `<span class="task-chip deadline">📅 ${escHtml(t.deadline_display)}</span>` : ""}
      ${t.group_name ? `<span class="task-chip group">💬 ${escHtml(t.group_name)}</span>` : ""}
      ${t.item_type ? `<span class="task-chip">${escHtml(t.item_type)}</span>` : ""}
    </div>
  </div>`;
}

/* ── TASK MODAL ── */
function openTaskModal(t) {
  document.getElementById("task-modal-title").textContent = t.title;
  document.getElementById("task-modal-group").textContent = (t.group_name || "") + " · " + (t.sender || "AI Extracted");
  document.getElementById("task-modal-raw").textContent = t.raw_message || "—";
  document.getElementById("task-modal-summary").textContent = t.summary || "—";
  const priority = ["high", "medium", "low"].includes(t.priority) ? t.priority : "low";
  const pLabel = priority === "high" ? "🔴 High" : priority === "medium" ? "🟡 Medium" : "🟢 Low";
  const elP = document.getElementById("task-modal-priority");
  elP.textContent = pLabel;
  elP.style.color = priorityColor(priority);
  document.getElementById("task-modal-deadline").textContent = t.deadline_display || "—";
  document.getElementById("task-modal-type").textContent = (t.item_type || "").replace(/^\w/, c => c.toUpperCase());
  openModal("modal-task");
}

/* ── EVENT CALENDAR WITH TOUCH & ORDERED EVENT DISPLAY ── */
function isTaskOnDate(task, y, m, d) {
  // Check exact ISO deadline
  if (task.deadline) {
    const dt = new Date(task.deadline);
    if (!isNaN(dt.getTime())) {
      if (dt.getFullYear() === y && dt.getMonth() === m && dt.getDate() === d) {
        return true;
      }
    }
  }

  // Check today / tomorrow relative matching
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === y && today.getMonth() === m;
  const isSelectedToday = isCurrentMonth && d === today.getDate();
  const isSelectedTomorrow = isCurrentMonth && d === (today.getDate() + 1);

  const disp = (task.deadline_display || "").toLowerCase();
  if (isSelectedToday && disp.includes("today")) return true;
  if (isSelectedTomorrow && disp.includes("tomorrow")) return true;

  return false;
}

function renderCalendar() {
  const y = state.calYear;
  const m = state.calMonth;
  const label = new Date(y, m).toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const mLabel = document.getElementById("cal-month-label");
  if (mLabel) mLabel.textContent = label;

  const grid = document.getElementById("cal-days-grid");
  if (!grid) return;

  const firstDay = new Date(y, m, 1).getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === y && today.getMonth() === m;

  let html = "";
  for (let i = 0; i < firstDay; i++) html += `<div class="cal-day empty"></div>`;
  for (let d = 1; d <= daysInMonth; d++) {
    const isToday = isCurrentMonth && d === today.getDate();
    const isSelected = state.selectedDate === d;
    const hasEvt = state.tasks.some(t => isTaskOnDate(t, y, m, d));
    html += `<div class="cal-day${isToday ? " today" : ""}${isSelected ? " selected" : ""}${hasEvt ? " has-event" : ""}" data-day="${d}">${d}</div>`;
  }
  grid.innerHTML = html;

  // Touch / click event listeners on every date cell
  grid.querySelectorAll(".cal-day:not(.empty)").forEach(el => {
    el.addEventListener("click", () => {
      const day = parseInt(el.dataset.day);
      selectCalDate(day);
    });
  });

  // Display initial events for selected date
  selectCalDate(state.selectedDate || today.getDate());
}

function selectCalDate(day) {
  state.selectedDate = day;
  const y = state.calYear;
  const m = state.calMonth;
  const dateObj = new Date(y, m, day);
  const label = dateObj.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  
  const elDate = document.getElementById("cal-selected-date");
  if (elDate) elDate.textContent = label;

  // Update visual selection ring on calendar grid
  document.querySelectorAll(".cal-day").forEach(el => {
    el.classList.toggle("selected", parseInt(el.dataset.day) === day);
  });

  // Filter tasks for this touched date
  const dayEvents = state.tasks.filter(t => isTaskOnDate(t, y, m, day));

  // Compute time & SORT CHRONOLOGICALLY IN ORDER
  const eventsWithTime = dayEvents.map(t => {
    const { minutes, timeStr } = extractEventTimeInfo(t);
    return { task: t, minutes, timeStr };
  });

  // Sort ascending by time (earlier in day first)
  eventsWithTime.sort((a, b) => a.minutes - b.minutes);

  const elCount = document.getElementById("cal-event-count");
  if (elCount) elCount.textContent = eventsWithTime.length;

  const panel = document.getElementById("cal-events-panel");
  if (!panel) return;

  if (eventsWithTime.length === 0) {
    panel.innerHTML = `<div class="empty-state" style="padding:40px 20px;text-align:center;">
      <div class="empty-icon" style="font-size:32px;margin-bottom:8px;">📅</div>
      <div class="empty-title" style="font-size:14px;font-weight:700;">No events on this date</div>
      <div class="empty-sub" style="font-size:12px;color:var(--text-muted);margin-top:4px;">
        Tap any date with a green dot to view scheduled deadlines and meetings.
      </div>
    </div>`;
    return;
  }

  // Render events in order with prominent time and full description
  panel.innerHTML = eventsWithTime.map(({ task: t, timeStr }) => {
    const pLabel = t.priority === "high" ? "🔴 High Priority" : t.priority === "medium" ? "🟡 Medium Priority" : "🟢 Low Priority";
    return `
      <div class="cal-event-card ${["high", "medium", "low"].includes(t.priority) ? t.priority : "low"}" data-id="${escHtml(t.id)}">
        <div class="cal-event-header">
          <span class="cal-event-time">⏰ ${escHtml(timeStr)}</span>
          <span class="task-priority-badge ${["high", "medium", "low"].includes(t.priority) ? t.priority : "low"}">${pLabel}</span>
        </div>
        <div class="cal-event-title">${escHtml(t.title)}</div>
        <div class="cal-event-desc">${escHtml(t.summary || t.action_item || t.raw_message)}</div>
        <div class="cal-event-footer">
          <span>💬 ${escHtml(t.group_name || 'WhatsApp Group')}</span>
          <span>👤 ${escHtml(t.sender || 'Contact')}</span>
          ${t.item_type ? `<span class="task-chip">${escHtml(t.item_type)}</span>` : ''}
        </div>
      </div>
    `;
  }).join("");

  // Clicking an event opens the task modal
  panel.querySelectorAll(".cal-event-card").forEach((el, idx) => {
    el.addEventListener("click", () => {
      openTaskModal(eventsWithTime[idx].task);
    });
  });
}

document.getElementById("cal-prev")?.addEventListener("click", () => {
  state.calMonth--;
  if (state.calMonth < 0) { state.calMonth = 11; state.calYear--; }
  state.selectedDate = Math.min(state.selectedDate, new Date(state.calYear, state.calMonth + 1, 0).getDate());
  renderCalendar();
});
document.getElementById("cal-next")?.addEventListener("click", () => {
  state.calMonth++;
  if (state.calMonth > 11) { state.calMonth = 0; state.calYear++; }
  state.selectedDate = Math.min(state.selectedDate, new Date(state.calYear, state.calMonth + 1, 0).getDate());
  renderCalendar();
});

/* ── SIMULATE MESSAGE ── */
const PRESETS = {
  college: { sender: "Prof. Ramanathan (HOD CSE)", msg: "Final submission for Cloud Computing Lab Records due tomorrow at 4:00 PM. No extensions will be granted. Bring signed physical copies.", group: "120363028192847@g.us|College CSE Final Year" },
  meeting: { sender: "Mentor Dr. Vikram", msg: "URGENT: Mandatory technical review meeting tomorrow at 11:30 AM in Audi 3. All team members must attend with presentation slides.", group: "120363099991234@g.us|Team Hacknova" },
  cultural: { sender: "Fest Committee", msg: "Annual Fest band auditions on Saturday 2 PM at College Auditorium. Register your group by Thursday midnight on the fest portal.", group: "120363028192847@g.us|College CSE Final Year" },
  bill: { sender: "Secretary Ravi", msg: "Attention: TNEB Electricity bill of ₹1,847 is due today. Please pay online via TNEB portal or UPI to avoid ₹200 late penalty.", group: "120363011122334@g.us|Apartment Residents" },
  work: { sender: "PM Anand", msg: "Client portal API is down in production. Critical hotfix needed tonight before midnight. All devs on call immediately.", group: "120363099991234@g.us|Team Hacknova" },
  delivery: { sender: "Amazon Logistics", msg: "Your Amazon return window closes tomorrow. Schedule a pickup today or drop off at nearest hub before 6 PM.", group: "120363088877665@g.us|Family Group" },
};

document.querySelectorAll(".preset-chip").forEach(btn => {
  btn.addEventListener("click", () => {
    const p = PRESETS[btn.dataset.preset];
    if (!p) return;
    document.getElementById("sim-message").value = p.msg;
    document.getElementById("sim-sender").value = p.sender;
    document.getElementById("sim-group").value = p.group;
  });
});

document.getElementById("btn-run-sim")?.addEventListener("click", async () => {
  const btn = document.getElementById("btn-run-sim");
  const msg = document.getElementById("sim-message").value.trim();
  const sender = document.getElementById("sim-sender").value.trim();
  const [groupJid, groupName] = document.getElementById("sim-group").value.split("|");
  if (!msg) { toast("Enter a message first", "⚠️"); return; }

  btn.textContent = "⏳ Processing with AI...";
  btn.disabled = true;

  const payload = {
    from: groupJid, sender, chatJid: groupJid, message: msg,
    text: msg, isFromMe: false, timestamp: Math.floor(Date.now() / 1000).toString(),
    groupName: groupName || "WhatsApp Group"
  };

  try {
    const response = await fetch(DAEMON + "/receive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (!result.task_id) throw new Error(result.reason || "Message was not accepted");
  } catch (_) {
    toast("Message was not processed. Start the local daemon and enable this group first.", "⚠️", 4500);
    btn.textContent = "🚀 Process with AI";
    btn.disabled = false;
    return;
  }

  await fetchTasks();
  await fetchSummaries();
  renderAll();

  closeModal("modal-simulate");
  toast("Message processed and categorized!", "🧠");
  btn.textContent = "🚀 Process with AI";
  btn.disabled = false;
});

/* ── DATABASE BACKED SEARCH ── */
let searchDebounceTimer = null;

document.getElementById("search-input")?.addEventListener("input", e => {
  const q = e.target.value.trim();
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);

  if (!q) {
    renderPriorityPanel();
    renderSummariesPanel();
    return;
  }

  searchDebounceTimer = setTimeout(async () => {
    try {
      const resp = await fetch(DAEMON + "/search?q=" + encodeURIComponent(q));
      if (resp.ok) {
        const data = await resp.json();
        const results = data.results || [];
        renderSearchResults(results, q);
        return;
      }
    } catch (_) {}

    // Local client-side fallback if daemon search fails
    const lower = q.toLowerCase();
    const filtered = state.tasks.filter(t =>
      (t.title || "").toLowerCase().includes(lower) ||
      (t.summary || "").toLowerCase().includes(lower) ||
      (t.group_name || "").toLowerCase().includes(lower) ||
      (t.raw_message || "").toLowerCase().includes(lower)
    );
    renderSearchResults(filtered, q);
  }, 250);
});

function renderSearchResults(items, query) {
  const panel = document.getElementById("priority-panel");
  const count = document.getElementById("priority-count");
  if (!panel) return;
  if (count) count.textContent = `${items.length} found`;

  if (!items.length) {
    panel.innerHTML = `<div class="empty-state">
      <div class="empty-icon">🔍</div>
      <div class="empty-title">No messages found</div>
      <div class="empty-sub">No database records matched "${escHtml(query)}".</div>
    </div>`;
    return;
  }

  panel.innerHTML = `
    <div style="font-size:11px;font-weight:700;color:var(--wa-green);margin-bottom:8px;text-transform:uppercase;">
      Search Results for "${escHtml(query)}" (${items.length})
    </div>
    ` + items.map(t => {
      const pColor = t.priority === "high" ? "#ea0038" : t.priority === "medium" ? "#f59e0b" : "var(--wa-green)";
      const title = t.title || t.content || "Message";
      const desc = t.summary || t.content || "";
      const group = t.group_name || "WhatsApp Chat";
      return `
        <div class="task-card" style="border-left:3px solid ${pColor};">
          <div class="task-card-top">
            <span class="task-title">${escHtml(title.substring(0, 60))}</span>
            <span class="task-priority-badge ${t.priority || 'low'}">${(t.priority || 'low').toUpperCase()}</span>
          </div>
          <div class="task-summary">${escHtml(desc.substring(0, 150))}</div>
          <div class="task-meta">
            <span class="task-chip group">💬 ${escHtml(group)}</span>
            ${t.deadline_display ? `<span class="task-chip deadline">⏰ ${escHtml(t.deadline_display)}</span>` : ''}
            <span class="task-chip">📅 ${relTime(t.created_at)}</span>
          </div>
        </div>
      `;
    }).join("");
}

/* ── RENDER ALL ── */
function renderAll() {
  renderStats();
  renderSummariesPanel();
  renderPriorityPanel();
  renderGroupsPanel();
  renderPriorityView();
  renderCalendar();
  renderWhitelist();
}

async function refreshAll() {
  const btn = document.getElementById("btn-refresh-all");
  if (btn) btn.classList.add("spinning");
  try {
    await Promise.all([
      checkDaemonStatus(),
      checkOllama(),
      fetchWhitelistGroups(),
      fetchTasks(),
      fetchSummaries()
    ]);
    renderAll();
  } finally {
    if (btn) btn.classList.remove("spinning");
  }
}

/* ── INIT ── */
document.addEventListener("DOMContentLoaded", async () => {
  // Clear any old tasks on start; only display live records or empty state
  state.tasks = [];
  state.summaries = [];
  renderAll();

  // Try to connect to the daemon and load any live data
  await refreshAll();

  // Periodic daemon health check + live data refresh
  state.daemonTimer = setInterval(async () => {
    await checkDaemonStatus();
    if (state.isLive || state.wa.connected) {
      await fetchTasks();
      await fetchSummaries();
      await fetchCalendar();
      renderAll();
    }
  }, 4000);

  // Ollama model health check
  setInterval(checkOllama, 10000);
});
