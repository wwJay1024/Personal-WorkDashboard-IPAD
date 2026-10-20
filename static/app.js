const state = {
  config: null,
  data: {
    notes: [],
    calendar: [],
  },
  sitting: null,
  sittingSyncedAt: 0,
  pendingSittingAction: null,
  socket: null,
  pollTimer: null,
  calendarMonth: new Date(),
};

const grid = document.querySelector("#dashboardGrid");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatSittingDuration(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const secs = Math.floor(safeSeconds % 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatSittingDurationLong(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  return `${hours} 小时 ${minutes} 分钟`;
}

function getAwayMinutes(sitting) {
  if (!sitting?.last_away_start) return null;
  const awayStart = new Date(sitting.last_away_start);
  if (Number.isNaN(awayStart.getTime())) return null;
  return Math.max(0, Math.floor((Date.now() - awayStart.getTime()) / 60000));
}

function syncSittingState(sitting) {
  state.sitting = sitting;
  state.sittingSyncedAt = Date.now();
  state.pendingSittingAction = null;
}

function getSittingElapsedSeconds() {
  return Math.max(0, Math.floor((Date.now() - (state.sittingSyncedAt || Date.now())) / 1000));
}

function getLiveSittingState() {
  const s = state.sitting;
  if (!s) return null;
  const elapsed = getSittingElapsedSeconds();
  const live = { ...s };

  if (live.status === "sitting") {
    live.accumulated_seconds = (s.accumulated_seconds || 0) + elapsed;
    live.today_sitting_seconds = (s.today_sitting_seconds || 0) + elapsed;
  } else if (live.status === "away") {
    live.away_elapsed_seconds = (s.away_elapsed_seconds || 0) + elapsed;
    live.today_break_seconds = (s.today_break_seconds || 0) + elapsed;
  }

  return live;
}

function widgetShell(component, body) {
  const size = component.size || "medium";
  return `
    <article class="widget ${escapeHtml(size)}" data-component="${escapeHtml(component.id)}">
      <div class="widget-header">
        <h2>${escapeHtml(component.title)}</h2>
      </div>
      <div class="widget-body">${body}</div>
    </article>
  `;
}

const renderers = {
  notes(component) {
    const notes = [...(state.data[component.data_type || "notes"] || [])]
      .sort((a, b) => Number(b.pinned) - Number(a.pinned))
      .slice(0, component.options?.limit || 6);
    const colors = ["rgba(184,212,240,0.35)", "rgba(200,230,201,0.35)"];
    const body = notes.length
      ? `<div class="notes-grid">${notes
          .map((note, index) => `<div class="note" style="background:${colors[index % 2]}">${escapeHtml(note.content)}</div>`)
          .join("")}</div>`
      : `<div class="empty">暂无便签</div>`;
    return widgetShell(component, body);
  },

  sitting(component) {
    const s = getLiveSittingState() || {};
    const status = s.status || "idle";
    const acc = s.accumulated_seconds || 0;
    const awayElapsed = s.away_elapsed_seconds || 0;
    const todaySitting = s.today_sitting_seconds || 0;
    const todayBreak = s.today_break_seconds || 0;
    const todaySittingDisplay = formatSittingDurationLong(todaySitting);
    const todayBreakDisplay = formatSittingDurationLong(todayBreak);

    const statusLabels = { idle: "未开始", sitting: "久坐中", away: "已离开" };
    const statusLabel = s.is_meeting ? `${statusLabels[status] || "未知"} · 开会中` : statusLabels[status] || "未知";
    const primaryAction = status === "idle" ? "start" : status === "away" ? "back" : "away";
    const primaryLabel = status === "idle" ? "我坐下了" : status === "away" ? "我回来了" : "我走了";
    const meetingAction = s.is_meeting ? "meeting_stop" : "meeting_start";
    const meetingLabel = s.is_meeting ? "结束会议" : "去开会";
    const isIdle = status === "idle";
    const isPending = Boolean(state.pendingSittingAction);
    const disabledAttr = isPending ? " disabled" : "";
    const idleDisabledAttr = isIdle || isPending ? " disabled" : "";
    const currentHHMM = `${String(Math.floor(acc / 3600)).padStart(2, "0")}:${String(Math.floor((acc % 3600) / 60)).padStart(2, "0")}`;
    const awayHHMM = `${String(Math.floor(awayElapsed / 3600)).padStart(2, "0")}:${String(Math.floor((awayElapsed % 3600) / 60)).padStart(2, "0")}`;

    const body = `
      <div class="sitting-card">
        <div class="sitting-stats">
          <div class="sitting-stat">
            <span class="sitting-stat-label">今日已久坐</span>
            <span class="sitting-stat-value" data-sitting-value="today-sitting">${escapeHtml(todaySittingDisplay)}</span>
          </div>
          <div class="sitting-stat">
            <span class="sitting-stat-label">今日已休息</span>
            <span class="sitting-stat-value" data-sitting-value="today-break">${escapeHtml(todayBreakDisplay)}</span>
          </div>
        </div>
        <div class="sitting-divider"></div>
        <div class="sitting-status sitting-status-${escapeHtml(status)}">
          <span class="sitting-dot"></span>
          <span data-sitting-value="status">${escapeHtml(statusLabel)}</span>
        </div>
        <div class="sitting-time-grid">
          <div class="sitting-time-block is-primary">
            <span class="sitting-time-label">当前久坐</span>
            <span class="sitting-timer" data-sitting-value="current">${currentHHMM}</span>
          </div>
          <div class="sitting-time-block ${status === "away" ? "is-active" : ""}">
            <span class="sitting-time-label">离开时长</span>
            <span class="sitting-timer" data-sitting-value="away">${awayHHMM}</span>
          </div>
        </div>
        <div class="sitting-controls">
          <button class="sitting-btn sitting-btn-primary" onclick="sittingAction('${primaryAction}')"${disabledAttr}>${escapeHtml(primaryLabel)}</button>
          <button class="sitting-btn sitting-btn-stop" onclick="sittingAction('stop')"${idleDisabledAttr}>结束计时</button>
          <button class="sitting-btn sitting-btn-meeting ${s.is_meeting ? "is-active" : ""}" onclick="sittingAction('${meetingAction}')"${idleDisabledAttr}>${escapeHtml(meetingLabel)}</button>
        </div>
      </div>
    `;

    const meetingOverlay = s.is_meeting ? `
      <div class="meeting-overlay is-visible" onclick="sittingAction('meeting_stop')">
        <div class="meeting-content">
          <span class="meeting-emoji">🧑🏻‍💻</span>
          <span class="meeting-text">开会中</span>
        </div>
        <button class="meeting-stop-btn">结束会议</button>
      </div>
    ` : "";

    return widgetShell(component, body) + meetingOverlay;
  },

  calendar(component) {
    const year = state.calendarMonth.getFullYear();
    const month = state.calendarMonth.getMonth();
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

    const firstDayOfMonth = new Date(year, month, 1);
    const firstDayWeekday = firstDayOfMonth.getDay(); // 0 = Sun, 1 = Mon
    // Find the Monday of the week containing the 1st of the month
    const mondayOffset = firstDayWeekday === 0 ? -6 : -(firstDayWeekday - 1);
    const startDate = new Date(year, month, 1 + mondayOffset);

    const itemsByDate = {};
    (state.data[component.data_type || "calendar"] || []).forEach((item) => {
      if (!itemsByDate[item.date]) itemsByDate[item.date] = [];
      itemsByDate[item.date].push(item);
    });

    // Generate 6 weeks × 5 weekdays = 30 cells
    const totalWeeks = 6;
    const days = [];
    for (let week = 0; week < totalWeeks; week++) {
      for (let weekday = 0; weekday < 5; weekday++) { // Mon=0 .. Fri=4
        const cellDate = new Date(startDate);
        cellDate.setDate(startDate.getDate() + week * 7 + weekday);

        const dayNum = cellDate.getDate();
        const cellMonth = cellDate.getMonth();
        const cellYear = cellDate.getFullYear();
        const dateStr = `${cellYear}-${String(cellMonth + 1).padStart(2, "0")}-${String(dayNum).padStart(2, "0")}`;
        const isOtherMonth = cellMonth !== month;

        days.push({
          dayNum,
          dateStr,
          isOtherMonth,
          isToday: dateStr === todayStr,
          items: itemsByDate[dateStr] || [],
        });
      }
    }

    const monthTitle = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long" }).format(state.calendarMonth);

    const body = `
      <div class="calendar-header">
        <div class="calendar-nav">
          <button class="calendar-nav-btn" onclick="changeCalendarMonth(-1)">&#8249;</button>
          <span class="calendar-title">${escapeHtml(monthTitle)}</span>
          <button class="calendar-nav-btn" onclick="changeCalendarMonth(1)">&#8250;</button>
        </div>
      </div>
      <div class="calendar-weekdays">
        ${["一","二","三","四","五"].map((d) => `<div class="calendar-weekday">${d}</div>`).join("")}
      </div>
      <div class="calendar-days">
        ${days.map((day) => {
          const itemHtml = day.items
            .map((item) => `<div class="calendar-day-item ${item.done ? "is-done" : ""}">${escapeHtml(item.text)}</div>`)
            .join("");
          const classes = [
            "calendar-day",
            day.isToday ? "is-today" : "",
            day.isOtherMonth ? "is-other-month" : "",
          ].filter(Boolean).join(" ");
          return `
            <div class="${classes}" ondblclick="openCalendarEditor('${day.dateStr}')">
              <div class="calendar-day-number">${day.dayNum}</div>
              <div class="calendar-day-items">${itemHtml}</div>
            </div>
          `;
        }).join("")}
      </div>
    `;

    return widgetShell(component, body);
  },
};

window.sittingAction = function (action) {
  if (state.pendingSittingAction && action !== "meeting_stop") return;

  const urls = {
    start: "/api/sitting/start",
    stop: "/api/sitting/stop",
    away: "/api/sitting/away",
    back: "/api/sitting/back",
    meeting_start: "/api/sitting/meeting/start",
    meeting_stop: "/api/sitting/meeting/stop",
  };

  if (urls[action]) {
    applyOptimisticSittingAction(action);
    const unlock = setTimeout(() => {
      if (state.pendingSittingAction) {
        state.pendingSittingAction = null;
        renderDashboard();
      }
    }, 5000);
    fetch(urls[action], { method: "POST" })
      .then((response) => {
        if (!response.ok) throw new Error(`${urls[action]} ${response.status}`);
        return fetchJson("/api/sitting/status");
      })
      .then((sitting) => {
        clearTimeout(unlock);
        syncSittingState(sitting);
        renderDashboard();
      })
      .catch(() => {
        clearTimeout(unlock);
        state.pendingSittingAction = null;
        loadInitial().catch(() => renderDashboard());
      });

  } else if (action === "take_break") {
    fetch("/api/sitting/reminder-response", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "take_break" }),
    });
    hideSittingReminder();
  } else if (action === "keep_working") {
    fetch("/api/sitting/reminder-response", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "keep_working" }),
    });
    hideSittingReminder();
  }
};

function applyOptimisticSittingAction(action) {
  const live = getLiveSittingState() || {};
  const nowIso = new Date().toISOString();
  let next = { ...live };

  if (action === "start") {
    next = {
      ...next,
      status: "sitting",
      is_sitting: true,
      is_away: false,
      is_meeting: false,
      current_session_start: nowIso,
      accumulated_seconds: 0,
      away_elapsed_seconds: 0,
      last_away_start: null,
    };
  } else if (action === "away" && live.status === "sitting") {
    next = {
      ...next,
      status: "away",
      is_away: true,
      current_session_start: null,
      last_away_start: nowIso,
      away_elapsed_seconds: 0,
    };
  } else if (action === "back" && live.status === "away") {
    const shouldReset = (live.away_elapsed_seconds || 0) >= 300;
    next = {
      ...next,
      status: "sitting",
      is_away: false,
      current_session_start: nowIso,
      last_away_start: null,
      away_elapsed_seconds: 0,
      accumulated_seconds: shouldReset ? 0 : live.accumulated_seconds || 0,
      today_sitting_seconds: live.today_sitting_seconds || 0,
    };
  } else if (action === "stop") {
    next = {
      ...next,
      status: "idle",
      is_sitting: false,
      is_away: false,
      is_meeting: false,
      current_session_start: null,
      accumulated_seconds: 0,
      last_away_start: null,
      away_elapsed_seconds: 0,
    };
  } else if (action === "take_break" && live.status === "sitting") {
    next = {
      ...next,
      status: "away",
      is_away: true,
      current_session_start: null,
      last_away_start: nowIso,
      away_elapsed_seconds: 0,
      show_reminder: false,
    };
  } else if (action === "meeting_start" && live.is_sitting && !live.is_meeting) {
    next = {
      ...next,
      is_meeting: true,
    };
  } else if (action === "meeting_stop" && live.is_meeting) {
    next = {
      ...next,
      is_meeting: false,
    };
  }

  state.pendingSittingAction = action;
  state.sitting = next;
  state.sittingSyncedAt = Date.now();
  renderDashboard();
}

function renderDashboard() {
  if (!state.config) return;
  grid.innerHTML = (state.config.components || [])
    .filter((component) => component.enabled !== false)
    .map((component) => {
      const renderer = renderers[component.type];
      return renderer ? renderer(component) : widgetShell(component, `<div class="empty">未知组件 ${escapeHtml(component.type)}</div>`);
    })
    .join("");
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  return response.json();
}

async function loadInitial() {
  const bootstrap = await fetchJson("/api/bootstrap");
  state.config = bootstrap.config;
  state.data = { ...state.data, ...bootstrap.data };
  syncSittingState(bootstrap.sitting);
  renderDashboard();
}

function connectSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws`);
  state.socket = socket;

  socket.addEventListener("open", () => {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
    socket.send("ping");
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "hello") {
      state.config = message.data.dashboard;
    }
    if (message.type === "data_update") {
      state.data[message.data_type] = message.data;
    }
    if (message.type === "config_update") {
      state.config = message.data;
    }
    if (message.type === "sitting_update") {
      syncSittingState(message.data);
    }
    if (message.type === "sitting_reminder") {
      showSittingReminder(message.data);
    }
    if (message.type === "reminder") {
      showBreakReminder(message.message, message.duration || 300);
    }
    renderDashboard();
  });

  socket.addEventListener("close", () => {
    if (!state.pollTimer) {
      state.pollTimer = setInterval(loadInitial, 15000);
    }
    setTimeout(connectSocket, 3000);
  });
}

function showBreakReminder(message, duration) {
  const overlay = document.querySelector("#breakOverlay");
  const messageEl = document.querySelector("#breakMessage");
  const countdown = document.querySelector("#breakCountdown");
  let remaining = duration;
  messageEl.textContent = message || "该休息一下了";
  overlay.classList.add("is-visible");
  overlay.setAttribute("aria-hidden", "false");

  const tick = () => {
    const minutes = String(Math.floor(remaining / 60)).padStart(2, "0");
    const seconds = String(remaining % 60).padStart(2, "0");
    countdown.textContent = `${minutes}:${seconds}`;
    remaining -= 1;
    if (remaining < 0) {
      clearInterval(timer);
      hideBreakReminder();
    }
  };
  tick();
  const timer = setInterval(tick, 1000);
  document.querySelector("#dismissBreak").onclick = () => {
    clearInterval(timer);
    hideBreakReminder();
  };
}

function hideBreakReminder() {
  const overlay = document.querySelector("#breakOverlay");
  overlay.classList.remove("is-visible");
  overlay.setAttribute("aria-hidden", "true");
}

function showSittingReminder(data) {
  const overlay = document.querySelector("#sittingReminderOverlay");
  const messageEl = document.querySelector("#sittingReminderMessage");
  if (!overlay || !messageEl) return;
  messageEl.textContent = data.message || "该休息一下了";
  overlay.classList.add("is-visible");
  overlay.setAttribute("aria-hidden", "false");
}

function hideSittingReminder() {
  const overlay = document.querySelector("#sittingReminderOverlay");
  if (!overlay) return;
  overlay.classList.remove("is-visible");
  overlay.setAttribute("aria-hidden", "true");
}

// Sitting timer updates every second
setInterval(() => {
  updateSittingTimers();
}, 1000);

function updateSittingTimers() {
  const s = getLiveSittingState();
  if (!s) return;

  const acc = s.accumulated_seconds || 0;
  const away = s.away_elapsed_seconds || 0;

  const values = {
    current: `${String(Math.floor(acc / 3600)).padStart(2, "0")}:${String(Math.floor((acc % 3600) / 60)).padStart(2, "0")}`,
    away: `${String(Math.floor(away / 3600)).padStart(2, "0")}:${String(Math.floor((away % 3600) / 60)).padStart(2, "0")}`,
    "today-sitting": formatSittingDurationLong(s.today_sitting_seconds || 0),
    "today-break": formatSittingDurationLong(s.today_break_seconds || 0),
  };

  Object.entries(values).forEach(([key, value]) => {
    const el = document.querySelector(`[data-sitting-value="${key}"]`);
    if (el && el.textContent !== value) {
      el.textContent = value;
    }
  });
}

window.changeCalendarMonth = function (delta) {
  const d = state.calendarMonth;
  state.calendarMonth = new Date(d.getFullYear(), d.getMonth() + delta, 1);
  renderDashboard();
};

window.openCalendarEditor = function (dateStr) {
  window.open(`/editor.html#calendar/${dateStr}`, "_blank");
};

loadInitial()
  .then(connectSocket)
  .catch((error) => {
    grid.innerHTML = `<article class="widget full"><div class="widget-body"><div class="empty">${escapeHtml(error.message)}</div></div></article>`;
  });
