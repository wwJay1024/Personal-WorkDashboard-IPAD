const editorState = {
  todos: [],
  schedule: [],
  notes: [],
  calendar: [],
  calendarMonth: new Date(),
  selectedDate: formatDateStr(new Date()),
};

const statusEl = document.querySelector("#editorStatus");
const recordsGrid = document.querySelector("#recordsGrid");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDateStr(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function localToIso(value) {
  return value ? new Date(value).toISOString() : null;
}

function combineDateTime(dateStr, timeStr) {
  if (!dateStr) return null;
  if (!timeStr) return new Date(dateStr + "T00:00:00").toISOString();
  return new Date(dateStr + "T" + timeStr + ":00").toISOString();
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function loadRecords() {
  const [todos, schedule, notes, calendar] = await Promise.all([
    api("/api/data/todos"),
    api("/api/data/schedule"),
    api("/api/data/notes"),
    api("/api/data/calendar"),
  ]);
  editorState.todos = todos;
  editorState.schedule = schedule;
  editorState.notes = notes;
  editorState.calendar = calendar;
  renderRecords();
  renderCalendarEditor();
  statusEl.textContent = "已同步";
}

function renderRecords() {
  recordsGrid.innerHTML = `
    ${renderGroup("待办", "todos", editorState.todos, (item) => `
      <strong>${escapeHtml(item.text)}</strong>
      <span>${escapeHtml(item.priority)} · ${item.done ? "已完成" : "进行中"}</span>
    `)}
    ${renderGroup("日程", "schedule", editorState.schedule, (item) => `
      <strong>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(new Date(item.start_time).toLocaleString("zh-CN"))}</span>
    `)}
    ${renderGroup("便签", "notes", editorState.notes, (item) => `
      <strong>${escapeHtml(item.pinned ? "置顶便签" : "便签")}</strong>
      <span>${escapeHtml(item.content)}</span>
    `)}
  `;
}

function renderGroup(title, type, records, content) {
  return `
    <div class="record-group">
      <h3>${title}</h3>
      ${
        records.length
          ? records
              .map(
                (item) => `
                  <div class="record-item">
                    ${content(item)}
                    <div class="record-actions">
                      ${type === "todos" ? `<button type="button" data-action="toggle" data-type="${type}" data-id="${item.id}">${item.done ? "重开" : "完成"}</button>` : ""}
                      <button type="button" data-action="delete" data-type="${type}" data-id="${item.id}">删除</button>
                    </div>
                  </div>
                `,
              )
              .join("")
          : `<div class="empty">暂无记录</div>`
      }
    </div>
  `;
}

async function handleSubmit(form, dataType, buildPayload) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusEl.textContent = "保存中";
    const formData = new FormData(form);
    const payload = buildPayload(formData);
    await api(`/api/data/${dataType}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    form.reset();
    await loadRecords();
  });
}

handleSubmit(document.querySelector("#todoForm"), "todos", (formData) => ({
  text: formData.get("text"),
  priority: formData.get("priority") || "medium",
  due_date: combineDateTime(formData.get("due_date_date"), formData.get("due_date_time")),
}));

handleSubmit(document.querySelector("#eventForm"), "schedule", (formData) => ({
  title: formData.get("title"),
  start_time: combineDateTime(formData.get("start_date"), formData.get("start_time")),
  location: formData.get("location") || null,
}));

handleSubmit(document.querySelector("#noteForm"), "notes", (formData) => ({
  content: formData.get("content"),
  pinned: formData.get("pinned") === "on",
}));

recordsGrid.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const { action, type, id } = button.dataset;
  statusEl.textContent = "更新中";
  if (action === "delete") {
    await api(`/api/data/${type}/${id}`, { method: "DELETE" });
  }
  if (action === "toggle") {
    const item = editorState[type].find((record) => record.id === id);
    await api(`/api/data/${type}/${id}`, {
      method: "PUT",
      body: JSON.stringify({ updates: { done: !item.done, updated_at: new Date().toISOString() } }),
    });
  }
  await loadRecords();
});

// ── Calendar Editor ──

function renderCalendarEditor() {
  const miniEl = document.querySelector("#calendarMini");
  if (!miniEl) return;

  const year = editorState.calendarMonth.getFullYear();
  const month = editorState.calendarMonth.getMonth();
  const today = new Date();
  const todayStr = formatDateStr(today);

  const firstDayOfMonth = new Date(year, month, 1);
  const firstDayWeekday = firstDayOfMonth.getDay();
  const mondayOffset = firstDayWeekday === 0 ? -6 : -(firstDayWeekday - 1);
  const startDate = new Date(year, month, 1 + mondayOffset);

  const itemsByDate = {};
  editorState.calendar.forEach((item) => {
    if (!itemsByDate[item.date]) itemsByDate[item.date] = [];
    itemsByDate[item.date].push(item);
  });

  const days = [];
  const totalWeeks = 6;
  for (let week = 0; week < totalWeeks; week++) {
    for (let weekday = 0; weekday < 5; weekday++) {
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
        isSelected: dateStr === editorState.selectedDate,
        items: itemsByDate[dateStr] || [],
      });
    }
  }

  const monthTitle = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long" }).format(editorState.calendarMonth);

  miniEl.innerHTML = `
    <div class="calendar-header">
      <div class="calendar-nav">
        <button class="calendar-nav-btn" onclick="changeEditorCalendarMonth(-1)">&#8249;</button>
        <span class="calendar-title">${escapeHtml(monthTitle)}</span>
        <button class="calendar-nav-btn" onclick="changeEditorCalendarMonth(1)">&#8250;</button>
      </div>
    </div>
    <div class="calendar-weekdays">
      ${["一","二","三","四","五"].map((d) => `<div class="calendar-weekday">${d}</div>`).join("")}
    </div>
    <div class="calendar-days">
      ${days.map((day) => {
        const classes = [
          "calendar-day",
          day.isToday ? "is-today" : "",
          day.isOtherMonth ? "is-other-month" : "",
          day.isSelected ? "is-selected" : "",
        ].filter(Boolean).join(" ");
        return `
          <div class="${classes}" onclick="selectCalendarDate('${day.dateStr}')">
            <div class="calendar-day-number">${day.dayNum}</div>
            <div class="calendar-day-items">${
              day.items
                .map((item) => `<div class="calendar-day-item ${item.done ? "is-done" : ""}">${escapeHtml(item.text)}</div>`)
                .join("")
            }</div>
          </div>
        `;
      }).join("")}
    </div>
  `;

  renderCalendarItems();
}

function renderCalendarItems() {
  const listEl = document.querySelector("#calendarItemsList");
  const dateTitle = document.querySelector("#calendarSelectedDate");
  if (!listEl || !dateTitle) return;

  dateTitle.textContent = editorState.selectedDate;

  // 日历待办：editorState.calendar 中 date == selectedDate 的项（原有逻辑保持不变）
  const calendarItems = editorState.calendar.filter(
    (item) => item.date === editorState.selectedDate
  );

  const renderCalendarRow = (item) => `
    <div class="calendar-list-item ${item.done ? "is-done" : ""}">
      <span class="calendar-item-text">${escapeHtml(item.text)}</span>
      <input type="checkbox" class="calendar-item-check" ${item.done ? "checked" : ""} onchange="toggleCalendarItem('${item.id}')">
      <button class="calendar-item-delete" onclick="deleteCalendarItem('${item.id}')">删除</button>
    </div>
  `;

  const calendarBlock = `
    <h4 class="calendar-group-title">日历待办</h4>
    ${
      calendarItems.length
        ? calendarItems.map(renderCalendarRow).join("")
        : `<div class="empty">暂无待办</div>`
    }
  `;

  listEl.innerHTML = calendarBlock;
}

window.changeEditorCalendarMonth = function (delta) {
  const d = editorState.calendarMonth;
  editorState.calendarMonth = new Date(d.getFullYear(), d.getMonth() + delta, 1);
  renderCalendarEditor();
};

window.selectCalendarDate = function (dateStr) {
  editorState.selectedDate = dateStr;
  renderCalendarEditor();
};

window.toggleCalendarItem = async function (id) {
  const item = editorState.calendar.find((r) => r.id === id);
  if (!item) return;
  await api(`/api/data/calendar/${id}`, {
    method: "PUT",
    body: JSON.stringify({ updates: { done: !item.done, updated_at: new Date().toISOString() } }),
  });
  await loadRecords();
};

window.deleteCalendarItem = async function (id) {
  await api(`/api/data/calendar/${id}`, { method: "DELETE" });
  await loadRecords();
};

document.querySelector("#calendarAddBtn")?.addEventListener("click", async () => {
  const input = document.querySelector("#calendarNewItem");
  const text = input.value.trim();
  if (!text) return;
  await api("/api/data/calendar", {
    method: "POST",
    body: JSON.stringify({ text, date: editorState.selectedDate }),
  });
  input.value = "";
  await loadRecords();
});

document.querySelector("#calendarNewItem")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    document.querySelector("#calendarAddBtn")?.click();
  }
});

// ── Tab Switching ──

const contentTab = document.querySelector("#contentTab");
const calendarTab = document.querySelector("#calendarTab");
const recordsPanel = document.querySelector("#recordsPanel");

document.querySelectorAll(".editor-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".editor-tab").forEach((t) => t.classList.remove("is-active"));
    tab.classList.add("is-active");
    const target = tab.dataset.tab;
    if (target === "content") {
      contentTab.style.display = "";
      recordsPanel.style.display = "";
      calendarTab.style.display = "none";
    } else {
      contentTab.style.display = "none";
      recordsPanel.style.display = "none";
      calendarTab.style.display = "";
      renderCalendarEditor();
    }
  });
});

// ── Route Hash ──

function parseHash() {
  const hash = window.location.hash;
  if (hash.startsWith("#calendar/")) {
    const dateStr = hash.slice("#calendar/".length);
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      editorState.selectedDate = dateStr;
      const [y, m] = dateStr.split("-").map(Number);
      editorState.calendarMonth = new Date(y, m - 1, 1);
      document.querySelectorAll(".editor-tab").forEach((t) => t.classList.remove("is-active"));
      const calendarTabBtn = document.querySelector('.editor-tab[data-tab="calendar"]');
      if (calendarTabBtn) calendarTabBtn.classList.add("is-active");
      contentTab.style.display = "none";
      recordsPanel.style.display = "none";
      calendarTab.style.display = "";
      renderCalendarEditor();
    }
  }
}

window.addEventListener("hashchange", parseHash);
parseHash();

loadRecords().catch((error) => {
  statusEl.textContent = error.message;
});
