const editorState = {
  notes: [],
  calendar: [],
  calendarMonth: new Date(),
  selectedDate: formatDateStr(new Date()),
};

const statusEl = document.querySelector("#editorStatus");
const notesListEl = document.querySelector("#notesList");

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

function setStatus(text) {
  statusEl.textContent = text;
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
  const [notes, calendar] = await Promise.all([api("/api/data/notes"), api("/api/data/calendar")]);
  editorState.notes = notes;
  editorState.calendar = calendar;
  renderNotes();
  renderCalendarEditor();
  setStatus("已同步");
}

// ── 便签 ──

function renderNotes() {
  const notes = [...editorState.notes].sort((a, b) => Number(b.pinned) - Number(a.pinned));
  notesListEl.innerHTML = notes.length
    ? notes
        .map(
          (note) => `
            <div class="note-row ${note.pinned ? "is-pinned" : ""}">
              <div>
                ${note.pinned ? `<span class="note-flag">置顶</span>` : ""}
                <p class="note-text">${escapeHtml(note.content)}</p>
              </div>
              <button type="button" class="note-delete" data-note-id="${escapeHtml(note.id)}">删除</button>
            </div>
          `,
        )
        .join("")
    : `<div class="empty">暂无便签</div>`;
}

document.querySelector("#noteForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const content = String(formData.get("content") || "").trim();
  if (!content) return;
  setStatus("保存中");
  await api("/api/data/notes", {
    method: "POST",
    body: JSON.stringify({ content, pinned: formData.get("pinned") === "on" }),
  });
  form.reset();
  await loadRecords();
});

notesListEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-note-id]");
  if (!button) return;
  setStatus("删除中");
  await api(`/api/data/notes/${button.dataset.noteId}`, { method: "DELETE" });
  await loadRecords();
});

// ── 日历 ──

function renderCalendarEditor() {
  const miniEl = document.querySelector("#calendarMini");
  if (!miniEl) return;

  const year = editorState.calendarMonth.getFullYear();
  const month = editorState.calendarMonth.getMonth();
  const todayStr = formatDateStr(new Date());

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

      const dateStr = formatDateStr(cellDate);
      days.push({
        dayNum: cellDate.getDate(),
        dateStr,
        isOtherMonth: cellDate.getMonth() !== month,
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
      ${["一", "二", "三", "四", "五"].map((d) => `<div class="calendar-weekday">${d}</div>`).join("")}
    </div>
    <div class="calendar-days">
      ${days
        .map((day) => {
          const classes = [
            "calendar-day",
            day.isToday ? "is-today" : "",
            day.isOtherMonth ? "is-other-month" : "",
            day.isSelected ? "is-selected" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return `
            <div class="${classes}" onclick="selectCalendarDate('${day.dateStr}')">
              <div class="calendar-day-number">${day.dayNum}</div>
              <div class="calendar-day-items">${day.items
                .map((item) => `<div class="calendar-day-item ${item.done ? "is-done" : ""}">${escapeHtml(item.text)}</div>`)
                .join("")}</div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;

  renderCalendarItems();
}

function renderCalendarItems() {
  const listEl = document.querySelector("#calendarItemsList");
  const dateTitle = document.querySelector("#calendarSelectedDate");
  if (!listEl || !dateTitle) return;

  dateTitle.textContent = editorState.selectedDate;

  const items = editorState.calendar.filter((item) => item.date === editorState.selectedDate);

  listEl.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="calendar-list-item ${item.done ? "is-done" : ""}">
              <span class="calendar-item-text">${escapeHtml(item.text)}</span>
              <input type="checkbox" class="calendar-item-check" ${item.done ? "checked" : ""} onchange="toggleCalendarItem('${item.id}')">
              <button class="calendar-item-delete" onclick="deleteCalendarItem('${item.id}')">删除</button>
            </div>
          `,
        )
        .join("")
    : `<div class="empty">当日暂无事项</div>`;
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
  const item = editorState.calendar.find((record) => record.id === id);
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

document.querySelector("#calendarAddBtn").addEventListener("click", async () => {
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

document.querySelector("#calendarNewItem").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    document.querySelector("#calendarAddBtn").click();
  }
});

// ── 从看板双击日期打开时定位到该日期 ──

function applyHashDate() {
  const hash = window.location.hash;
  if (!hash.startsWith("#calendar/")) return;
  const dateStr = hash.slice("#calendar/".length);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return;
  editorState.selectedDate = dateStr;
  const [y, m] = dateStr.split("-").map(Number);
  editorState.calendarMonth = new Date(y, m - 1, 1);
  renderCalendarEditor();
}

window.addEventListener("hashchange", applyHashDate);
applyHashDate();

loadRecords().catch((error) => {
  setStatus(error.message);
});
