const API = "/api/v1/exam/math-profile";
const AI_API = "/api/v1/ai";
const AUTH_API = "/api/v1/auth";
const USERS_API = "/api/v1/users";
const AUTH_STORAGE_KEY = "vector-auth-session";

function readStoredTokens() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(AUTH_STORAGE_KEY) || "null");
    if (stored?.access_token && stored?.refresh_token) return stored;
  } catch {
    try { sessionStorage.removeItem(AUTH_STORAGE_KEY); } catch { /* Storage may be unavailable. */ }
  }
  return null;
}

const storedTokens = readStoredTokens();

const state = {
  role: "student",
  auth: {
    accessToken: storedTokens?.access_token || null,
    refreshToken: storedTokens?.refresh_token || null,
    user: null,
    refreshPromise: null,
    generation: 0,
    busy: false,
  },
  page: "dashboard",
  overview: null,
  tasks: [],
  completedTheory: [],
  analytics: null,
  roadmap: null,
  lesson: null,
  homework: null,
  dashboard: null,
  admin: null,
  adminUsers: [],
  adminTasks: [],
  currentTask: 0,
  practiceFilter: "all",
  focusTheory: null,
  lessonView: null,
  lessonTheoryPage: 0,
  lessonTheoryUnitId: null,
  aiStatus: null,
  aiTheoryAnswers: {},
  aiTheoryChecks: {},
  aiHints: {},
  dashboardSelectedDate: null,
  dashboardCalendarMonth: null,
};

const view = document.querySelector("#view");

function apiErrorMessage(payload) {
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail) && payload.detail.length) {
    return payload.detail[0].msg || "Проверьте введённые данные";
  }
  return "Не удалось получить данные";
}

function persistTokens(tokens) {
  state.auth.accessToken = tokens.access_token;
  state.auth.refreshToken = tokens.refresh_token;
  try { sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  })); } catch { /* Keep this session in memory if browser storage is blocked. */ }
}

function clearTokens() {
  state.auth.accessToken = null;
  state.auth.refreshToken = null;
  try { sessionStorage.removeItem(AUTH_STORAGE_KEY); } catch { /* Storage may be unavailable. */ }
}

function assertCurrentSession(generation) {
  if (generation !== state.auth.generation) {
    const error = new Error("Запрос относится к завершённой сессии.");
    error.silent = true;
    throw error;
  }
}

async function refreshTokens() {
  if (!state.auth.refreshToken) return false;
  if (state.auth.refreshPromise) return state.auth.refreshPromise;
  const generation = state.auth.generation;
  const refreshToken = state.auth.refreshToken;
  const pending = (async () => {
    const response = await fetch(`${AUTH_API}/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal: AbortSignal.timeout(15000),
    });
    const payload = await response.json().catch(() => ({}));
    assertCurrentSession(generation);
    if (!response.ok || state.auth.refreshToken !== refreshToken) return false;
    persistTokens(payload.data);
    return true;
  })().catch(() => false).finally(() => {
    if (state.auth.refreshPromise === pending) state.auth.refreshPromise = null;
  });
  state.auth.refreshPromise = pending;
  return pending;
}

async function requestFrom(baseUrl, path, options = {}) {
  const generation = state.auth.generation;
  const { skipAuth = false, retryAuth = true, ...fetchOptions } = options;
  const headers = { "Content-Type": "application/json", ...(fetchOptions.headers || {}) };
  if (!skipAuth && state.auth.accessToken) headers.Authorization = `Bearer ${state.auth.accessToken}`;
  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...fetchOptions, headers, signal: fetchOptions.signal || AbortSignal.timeout(35000),
    });
  } catch (error) {
    assertCurrentSession(generation);
    throw new Error(error.name === "TimeoutError"
      ? "Сервер отвечает слишком долго. Попробуйте ещё раз."
      : "Не удалось связаться с сервером. Проверьте подключение и повторите действие.");
  }
  assertCurrentSession(generation);
  if (response.status === 401 && !skipAuth && retryAuth) {
    const refreshed = await refreshTokens();
    assertCurrentSession(generation);
    if (refreshed) return requestFrom(baseUrl, path, { ...fetchOptions, retryAuth: false });
  }
  const payload = await response.json().catch(() => ({}));
  assertCurrentSession(generation);
  if (response.status === 401 && !skipAuth) {
    endLocalSession("Сессия завершилась. Войдите снова.");
    const error = new Error("Сессия завершилась. Войдите снова.");
    error.silent = true;
    throw error;
  }
  if (!response.ok) throw new Error(apiErrorMessage(payload));
  return payload.data;
}

function request(path, options = {}) {
  return requestFrom(API, path, options);
}

function aiRequest(path, options = {}) {
  return requestFrom(AI_API, path, options);
}

function userRequest(path, options = {}) {
  return requestFrom(USERS_API, path, options);
}

async function loadData() {
  const generation = state.auth.generation;
  const [overview, tasks, completedTheory, analytics, roadmap, lesson, homework, dashboard, aiStatus] =
    await Promise.all([
      request("/overview"), request("/tasks"),
      request(`/theory/completed`),
      request(`/analytics`),
      request(`/roadmap`),
      request(`/lesson/current`),
      request(`/homework/current`),
      request(`/dashboard`),
      aiRequest("/status").catch(() => ({ provider: "deepseek", model: "—", configured: false, capabilities: [] })),
    ]);
  assertCurrentSession(generation);
  Object.assign(state, { overview, tasks, completedTheory, analytics, roadmap, lesson, homework, dashboard, aiStatus });
  if (state.role === "admin") {
    const [admin, adminUsers, adminTasks] = await Promise.all([
      request("/admin/dashboard"), request("/admin/users"), request("/admin/tasks"),
    ]);
    assertCurrentSession(generation);
    Object.assign(state, { admin, adminUsers, adminTasks });
  } else {
    Object.assign(state, { admin: null, adminUsers: [], adminTasks: [] });
  }
  state.dashboardSelectedDate ||= dashboard.date;
  state.dashboardCalendarMonth ||= `${dashboard.date.slice(0, 7)}-01`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[char]));
}

function safeUrl(value) {
  try {
    const url = new URL(String(value), window.location.origin);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return "#";
    return escapeHtml(url.href);
  } catch { return "#"; }
}

function safeColor(value) {
  return /^#[0-9a-f]{6}$/i.test(String(value)) ? value : "#267468";
}

function scrollBehavior() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

function difficultyLabel(value) {
  return { basic: "Базовый", standard: "Средний", advanced: "Повышенный", expert: "Сложный" }[value] || escapeHtml(value);
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" }).format(new Date(value));
}

function formatLongDate(value) {
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "long", day: "numeric", month: "long",
  }).format(new Date(`${value}T12:00:00`));
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function attemptCount(value) {
  const word = { one: "попытка", few: "попытки", many: "попыток", other: "попытки" }[new Intl.PluralRules("ru").select(value)];
  return `${escapeHtml(value)} ${word}`;
}

function percent(value) {
  return value === null || value === undefined ? "—" : `${value}%`;
}

function toast(message) {
  if (message === "Запрос относится к завершённой сессии." || message === "Сессия завершилась. Войдите снова.") return;
  const region = document.querySelector("#toast-region");
  const item = document.createElement("div");
  item.className = "toast";
  item.textContent = message;
  region.append(item);
  setTimeout(() => item.remove(), 3200);
}

function pageHeader(title, description = "", action = "") {
  return `<header class="page-header">
    <div><h1>${escapeHtml(title)}</h1>${description ? `<p>${escapeHtml(description)}</p>` : ""}</div>
    ${action ? `<div class="header-action">${action}</div>` : ""}
  </header>`;
}

function localDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 12);
}

function isoDate(year, monthIndex, day) {
  const date = new Date(year, monthIndex, day, 12);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function shiftCalendarMonth(value, offset) {
  const date = localDate(value);
  return isoDate(date.getFullYear(), date.getMonth() + offset, 1);
}

function formatCalendarMonth(value) {
  return new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" }).format(localDate(value));
}

function roadmapLessonState(item, subtopic, index) {
  if (item.lesson_state === "completed" || subtopic.state === "completed") return "completed";
  if (item.lesson_state === "upcoming") return "locked";
  const currentIndex = item.subtopics.findIndex((lesson) => lesson.state !== "completed");
  return index === Math.max(0, currentIndex) ? "current" : "available";
}

function renderRoadmapLesson(item, subtopic, index) {
  const lessonState = roadmapLessonState(item, subtopic, index);
  const statusLabels = { completed: "Пройден", current: "Текущий", available: "Открыт", locked: "Закрыт" };
  const statusIcons = { completed: "✓", current: "→", available: "↗", locked: "⌑" };
  const status = lessonState === "available" ? "" : `<span class="lesson-window-status"><i aria-hidden="true">${statusIcons[lessonState]}</i>${statusLabels[lessonState]}</span>`;
  const canOpen = item.lesson_state === "current" && lessonState !== "completed";
  const tag = canOpen ? "button" : "article";
  const attributes = canOpen
    ? `type="button" data-roadmap-lesson="${index}" aria-label="Открыть урок ${escapeHtml(subtopic.title)}"`
    : `aria-label="Урок ${escapeHtml(subtopic.title)}: ${statusLabels[lessonState].toLowerCase()}"`;
  const footer = canOpen
    ? `<span class="lesson-window-action">Открыть урок <b aria-hidden="true">→</b></span>`
    : "";

  return `<${tag} class="lesson-window ${lessonState}" ${attributes}>
    <span class="lesson-window-top"><span class="lesson-number">Урок ${String(subtopic.order).padStart(2, "0")}</span>${status}</span>
    <h3>${escapeHtml(subtopic.title)}</h3>
    ${lessonState === "current" || lessonState === "available" ? `<span class="lesson-window-progress"><span><b>${escapeHtml(subtopic.progress)}%</b></span><i role="progressbar" aria-label="Прогресс урока ${escapeHtml(subtopic.title)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${escapeHtml(subtopic.progress)}"><b style="width:${escapeHtml(subtopic.progress)}%"></b></i></span>` : ""}
    ${footer}
  </${tag}>`;
}

function renderRoadmapTopic(item) {
  const taskNumbers = item.task_numbers.map((number) => `<span>№${number}</span>`).join("");
  return `<section class="roadmap-topic-section ${escapeHtml(item.lesson_state)}" aria-labelledby="roadmap-topic-${escapeHtml(item.position)}">
    <header class="roadmap-topic-header">
      <div class="roadmap-topic-heading">
        <span class="roadmap-topic-position">${item.lesson_state === "completed" ? "✓" : item.lesson_state === "upcoming" ? "🔒" : String(item.position).padStart(2, "0")}</span>
        <div><h2 id="roadmap-topic-${escapeHtml(item.position)}">${escapeHtml(item.topic.short_title)}</h2></div>
      </div>
      <div class="roadmap-topic-progress"><span><b>${escapeHtml(item.progress)}%</b> темы</span><i role="progressbar" aria-label="Прогресс темы ${escapeHtml(item.topic.short_title)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${escapeHtml(item.progress)}"><b style="width:${escapeHtml(item.progress)}%"></b></i></div>
    </header>
    <div class="roadmap-topic-info"><div class="roadmap-task-numbers" aria-label="Задания ЕГЭ">${taskNumbers}</div></div>
    <div class="lesson-window-grid">${item.subtopics.map((subtopic, index) => renderRoadmapLesson(item, subtopic, index)).join("")}</div>
  </section>`;
}

function renderDashboardCalendar(data) {
  const monthDate = localDate(state.dashboardCalendarMonth);
  const firstOffset = (new Date(monthDate.getFullYear(), monthDate.getMonth(), 1, 12).getDay() + 6) % 7;
  const daysInMonth = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0, 12).getDate();
  const planDates = new Set(data.schedule.map((item) => item.date));
  planDates.add(data.date);
  const cells = [
    ...Array.from({ length: firstOffset }, () => '<span class="calendar-day empty" aria-hidden="true"></span>'),
    ...Array.from({ length: daysInMonth }, (_, index) => {
      const day = index + 1;
      const value = isoDate(monthDate.getFullYear(), monthDate.getMonth(), day);
      const classes = [
        "calendar-day",
        value === data.date ? "today" : "",
        value === state.dashboardSelectedDate ? "selected" : "",
        planDates.has(value) ? "has-plan" : "",
      ].filter(Boolean).join(" ");
      return `<button class="${classes}" data-calendar-date="${value}" aria-pressed="${value === state.dashboardSelectedDate}" aria-label="${formatLongDate(value)}"><span>${day}</span>${planDates.has(value) ? "<i></i>" : ""}</button>`;
    }),
  ];
  return `<div class="calendar-card">
    <div class="calendar-toolbar"><button class="calendar-arrow" data-calendar-shift="-1" aria-label="Предыдущий месяц">←</button><b>${formatCalendarMonth(state.dashboardCalendarMonth)}</b><button class="calendar-arrow" data-calendar-shift="1" aria-label="Следующий месяц">→</button></div>
    <div class="calendar-weekdays">${["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => `<span>${day}</span>`).join("")}</div>
    <div class="calendar-grid">${cells.join("")}</div>
  </div>`;
}

function renderLessonPlanCard(lesson) {
  if (!lesson) return `<article class="day-plan-card empty"><span class="agenda-kind">Урок</span><h3>Курс пройден</h3><button class="secondary-button" data-go="roadmap">Посмотреть роадмап</button></article>`;
  return `<article class="day-plan-card lesson">
    <div class="day-plan-card-top"><span class="agenda-kind">Текущий урок</span><span>${escapeHtml(lesson.estimated_minutes)} мин</span></div>
    <h3>${escapeHtml(lesson.title)}</h3>
    <div class="lesson-progress"><div><span>Прогресс урока</span><b>${escapeHtml(lesson.progress)}%</b></div><i role="progressbar" aria-label="Прогресс урока ${escapeHtml(lesson.title)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${escapeHtml(lesson.progress)}"><b style="width:${escapeHtml(lesson.progress)}%"></b></i></div>
    <div class="day-plan-card-footer"><span>${escapeHtml(lesson.step_label)}</span><button class="primary-button" data-go="lessons">Продолжить урок →</button></div>
  </article>`;
}

function renderTodayPlan(data) {
  const homework = data.today.homework;
  const homeworkCard = homework
    ? `<article class="day-plan-card homework"><div class="day-plan-card-top"><span class="agenda-kind">Домашнее задание</span><span>до ${formatDate(homework.due_date)}</span></div><h3>${escapeHtml(homework.title)}</h3><div class="lesson-progress"><div><span>Выполнено</span><b>${escapeHtml(homework.progress)}%</b></div><i role="progressbar" aria-label="Прогресс домашнего задания" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${escapeHtml(homework.progress)}"><b style="width:${escapeHtml(homework.progress)}%"></b></i></div><div class="day-plan-card-footer"><span>${escapeHtml(homework.estimated_minutes)} мин</span><button class="secondary-button" data-go="homework">Открыть ДЗ →</button></div></article>`
    : `<article class="day-plan-card homework empty"><span class="agenda-kind">Домашнее задание</span><h3>Пока не назначено</h3></article>`;
  const reviews = data.today.reviews.map((item) => `<article class="agenda-row review"><span>Повторение</span><div><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.action)}</small></div><button class="schedule-arrow" data-go="lessons" aria-label="Открыть повторение">→</button></article>`).join("");
  return `<div class="day-plan-cards">${renderLessonPlanCard(data.today.lesson)}${homeworkCard}${reviews}</div>`;
}

function renderScheduledPlan(data, selectedDate) {
  const labels = { lesson: "Урок", homework: "Домашнее задание", review: "Повторение" };
  const items = data.schedule.filter((item) => item.date === selectedDate);
  if (!items.length) return '<div class="selected-day-empty"><span>Нет занятий</span></div>';
  return `<div class="agenda-list">${items.map((item) => `<article class="agenda-row ${escapeHtml(item.kind)}"><span>${labels[item.kind]}</span><div><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.detail)}</small>${Number.isInteger(item.progress) ? `<i><b style="width:${escapeHtml(item.progress)}%"></b></i>` : ""}</div><button class="schedule-arrow" data-go="${item.kind === "homework" ? "homework" : "lessons"}" aria-label="Открыть ${labels[item.kind].toLowerCase()}">→</button></article>`).join("")}</div>`;
}

function renderDashboard() {
  const data = state.dashboard;
  const metrics = data.metrics;
  const selectedDate = state.dashboardSelectedDate || data.date;
  const isToday = selectedDate === data.date;
  const score = metrics.prediction_available ? metrics.expected_test_score : "—";
  view.innerHTML = `${pageHeader("Учебный маршрут", "")}
    <section class="section dashboard-calendar-section">
      <div class="section-heading"><div><h2>Расписание</h2></div>${isToday ? "" : '<button class="secondary-button compact-button" data-calendar-today>Сегодня</button>'}</div>
      <div class="calendar-layout">${renderDashboardCalendar(data)}
        <div class="selected-day-plan"><div class="selected-day-heading"><div><h3>${formatLongDate(selectedDate)}</h3></div></div>
          ${isToday ? renderTodayPlan(data) : renderScheduledPlan(data, selectedDate)}
        </div>
      </div>
    </section>

    <section class="dashboard-overview" aria-label="Общие сведения об обучении">
      ${metrics.prediction_available ? `<article><span>Прогноз ЕГЭ</span><b>${score}<small> / ${metrics.max_test_score}</small></b></article>` : ""}
      <article><span>Серия занятий</span><b>${metrics.streak_days}<small> дн.</small></b></article>
    </section>`;

  document.querySelectorAll("[data-calendar-date]").forEach((button) => button.addEventListener("click", () => {
    state.dashboardSelectedDate = button.dataset.calendarDate;
    renderDashboard();
    document.querySelector(`[data-calendar-date="${state.dashboardSelectedDate}"]`)?.focus({ preventScroll: true });
  }));
  document.querySelectorAll("[data-calendar-shift]").forEach((button) => button.addEventListener("click", () => {
    state.dashboardCalendarMonth = shiftCalendarMonth(state.dashboardCalendarMonth, Number(button.dataset.calendarShift));
    const shift = button.dataset.calendarShift;
    state.dashboardSelectedDate = state.dashboardCalendarMonth.slice(0, 7) === data.date.slice(0, 7) ? data.date : state.dashboardCalendarMonth;
    renderDashboard();
    document.querySelector(`[data-calendar-shift="${shift}"]`)?.focus({ preventScroll: true });
  }));
  document.querySelector("[data-calendar-today]")?.addEventListener("click", () => {
    state.dashboardSelectedDate = data.date;
    state.dashboardCalendarMonth = `${data.date.slice(0, 7)}-01`;
    renderDashboard();
  });
  bindGoButtons();
}

function renderRoadmap() {
  const roadmap = state.roadmap;
  const completedLessons = roadmap.lesson_order.flatMap((item) => item.subtopics).filter((lesson) => lesson.state === "completed").length;
  const totalLessons = roadmap.lesson_order.reduce((total, item) => total + item.subtopics.length, 0);
  view.innerHTML = `${pageHeader("Темы и уроки", `${completedLessons} из ${totalLessons} уроков пройдено`)}
    <section class="roadmap-course" aria-label="Учебный маршрут по темам">

      <div class="roadmap-topic-sections">${roadmap.lesson_order.map(renderRoadmapTopic).join("")}</div>
    </section>`;
  document.querySelectorAll("[data-roadmap-lesson]").forEach((button) => button.addEventListener("click", () => {
    if (state.lesson.status !== "active") return;
    const sections = state.lesson.theory.sections || [];
    if (sections.length) {
      state.lessonTheoryUnitId = state.lesson.unit_id;
      state.lessonTheoryPage = Math.min(Number(button.dataset.roadmapLesson), sections.length - 1);
    }
    state.lessonView = state.lesson.current_step === "practice" ? "theory" : null;
    goTo("lessons");
  }));
}

function theoryDiagram(type) {
  if (type === "coordinate-grid") {
    return `<figure class="theory-diagram coordinate-diagram">
      <svg viewBox="0 0 420 250" role="img" aria-labelledby="coordinate-diagram-title coordinate-diagram-desc">
        <title id="coordinate-diagram-title">Координаты вектора по клеткам</title>
        <desc id="coordinate-diagram-desc">Вектор направлен на четыре клетки вправо и на три клетки вверх.</desc>
        <defs><marker id="vector-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z"></path></marker></defs>
        <g class="diagram-grid">${Array.from({ length: 9 }, (_, index) => `<line x1="${50 + index * 38}" y1="28" x2="${50 + index * 38}" y2="218"></line>`).join("")}${Array.from({ length: 6 }, (_, index) => `<line x1="50" y1="${28 + index * 38}" x2="354" y2="${28 + index * 38}"></line>`).join("")}</g>
        <line class="diagram-axis" x1="50" y1="218" x2="380" y2="218" marker-end="url(#vector-arrow)"></line>
        <line class="diagram-axis" x1="50" y1="232" x2="50" y2="14" marker-end="url(#vector-arrow)"></line>
        <line class="diagram-guide" x1="88" y1="180" x2="240" y2="180"></line>
        <line class="diagram-guide" x1="240" y1="180" x2="240" y2="66"></line>
        <line class="diagram-vector" x1="88" y1="180" x2="240" y2="66" marker-end="url(#vector-arrow)"></line>
        <circle class="diagram-point" cx="88" cy="180" r="5"></circle><circle class="diagram-point" cx="240" cy="66" r="5"></circle>
        <text x="103" y="199">Δx = +4</text><text x="249" y="130">Δy = +3</text><text class="diagram-answer" x="250" y="48">a = (4; 3)</text>
        <text x="382" y="222">x</text><text x="39" y="16">y</text>
      </svg>
      <figcaption>Смотрите не на положение стрелки, а на её перемещение: вправо +4, вверх +3.</figcaption>
    </figure>`;
  }
  if (type === "operation-flow") {
    return `<figure class="theory-diagram operation-diagram" aria-label="Порядок вычисления линейной комбинации">
      <div class="operation-node"><small>1 · коэффициенты</small><b>a + 3b</b></div><span>→</span>
      <div class="operation-node"><small>2 · координаты</small><b>(2 + 3·1; 0 + 3·4)</b></div><span>→</span>
      <div class="operation-node accent"><small>3 · новый вектор</small><b>(5; 12)</b></div>
      <figcaption>Не ищите длину раньше времени: сначала получите один новый вектор.</figcaption>
    </figure>`;
  }
  if (type === "scalar-angle") {
    return `<figure class="theory-diagram scalar-diagram">
      <svg viewBox="0 0 420 230" role="img" aria-labelledby="scalar-diagram-title scalar-diagram-desc">
        <title id="scalar-diagram-title">Угол между двумя векторами</title>
        <desc id="scalar-diagram-desc">Два вектора имеют общее начало и образуют угол альфа.</desc>
        <defs><marker id="scalar-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z"></path></marker></defs>
        <line class="diagram-vector" x1="72" y1="184" x2="350" y2="184" marker-end="url(#scalar-arrow)"></line>
        <line class="diagram-vector warm" x1="72" y1="184" x2="250" y2="55" marker-end="url(#scalar-arrow)"></line>
        <path class="diagram-angle" d="M132 184 A60 60 0 0 0 121 149"></path>
        <text class="diagram-answer" x="137" y="159">α</text><text x="342" y="208">a</text><text x="250" y="48">b</text>
        <text class="diagram-formula" x="103" y="92">a · b = |a|·|b|·cos α</text>
      </svg>
      <figcaption>Оба вектора мысленно отложены от одной точки — только тогда виден угол между ними.</figcaption>
    </figure>`;
  }
  if (type === "geometry-triangle") {
    return `<figure class="theory-diagram geometry-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="triangle-diagram-title triangle-diagram-desc">
        <title id="triangle-diagram-title">Прямоугольный треугольник</title><desc id="triangle-diagram-desc">Катеты 6 и 8, гипотенуза 10.</desc>
        <path class="geometry-fill" d="M82 194 L82 54 L330 194 Z"></path><path class="geometry-shape" d="M82 194 L82 54 L330 194 Z"></path>
        <path class="geometry-guide" d="M82 174 L102 174 L102 194"></path>
        <text x="52" y="127">6</text><text x="196" y="220">8</text><text class="diagram-answer" x="217" y="111">10</text>
        <text class="diagram-formula" x="153" y="42">6² + 8² = 10²</text>
      </svg><figcaption>Сначала найдите прямой угол, затем подпишите катеты и гипотенузу.</figcaption>
    </figure>`;
  }
  if (type === "geometry-trapezoid") {
    return `<figure class="theory-diagram geometry-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="trapezoid-diagram-title trapezoid-diagram-desc">
        <title id="trapezoid-diagram-title">Трапеция с высотой</title><desc id="trapezoid-diagram-desc">Основания 6 и 14, высота 4.</desc>
        <path class="geometry-fill warm" d="M70 192 L122 72 L296 72 L350 192 Z"></path><path class="geometry-shape" d="M70 192 L122 72 L296 72 L350 192 Z"></path>
        <line class="geometry-guide dashed" x1="122" y1="72" x2="122" y2="192"></line><path class="geometry-guide" d="M122 174 L140 174 L140 192"></path>
        <text x="194" y="57">6</text><text x="198" y="217">14</text><text class="diagram-answer" x="91" y="136">h = 4</text>
        <text class="diagram-formula" x="128" y="126">S = (a + b)h / 2</text>
      </svg><figcaption>В формулу площади входит перпендикулярная основаниям высота, а не боковая сторона.</figcaption>
    </figure>`;
  }
  if (type === "geometry-circle") {
    return `<figure class="theory-diagram geometry-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="circle-diagram-title circle-diagram-desc">
        <title id="circle-diagram-title">Сектор круга и касательная</title><desc id="circle-diagram-desc">Радиусы образуют сектор, касательная перпендикулярна радиусу.</desc>
        <circle class="geometry-fill" cx="178" cy="124" r="82"></circle><circle class="geometry-shape" cx="178" cy="124" r="82"></circle>
        <path class="geometry-sector" d="M178 124 L178 42 A82 82 0 0 1 249 165 Z"></path>
        <line class="geometry-shape" x1="178" y1="124" x2="178" y2="42"></line><line class="geometry-shape" x1="178" y1="124" x2="249" y2="165"></line>
        <line class="geometry-guide warm" x1="260" y1="42" x2="260" y2="206"></line><path class="geometry-guide" d="M244 58 L260 58 L260 42"></path>
        <text x="187" y="84">R</text><text class="diagram-answer" x="205" y="139">α</text><text x="274" y="119">касательная</text>
      </svg><figcaption>Угол сектора задаёт долю круга; радиус в точку касания образует 90°.</figcaption>
    </figure>`;
  }
  if (type === "geometry-prism") {
    return `<figure class="theory-diagram geometry-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="prism-diagram-title prism-diagram-desc">
        <title id="prism-diagram-title">Прямая призма</title><desc id="prism-diagram-desc">Площадь основания умножается на высоту.</desc>
        <path class="geometry-fill" d="M90 176 L210 204 L314 154 L195 127 Z"></path>
        <path class="geometry-shape" d="M90 176 L210 204 L314 154 L195 127 Z M90 176 L90 70 L210 98 L314 48 L314 154 M90 70 L210 98 L314 48 M210 98 L210 204"></path>
        <line class="geometry-guide dashed warm" x1="333" y1="48" x2="333" y2="154"></line>
        <text class="diagram-answer" x="341" y="106">h</text><text x="155" y="174">Sосн</text>
        <text class="diagram-formula" x="105" y="37">V = Sосн · h</text>
      </svg><figcaption>Для призмы нужен полный столб высоты; для пирамиды результат дополнительно делят на 3.</figcaption>
    </figure>`;
  }
  if (type === "geometry-solids") {
    return `<figure class="theory-diagram geometry-diagram solids-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="solids-diagram-title solids-diagram-desc">
        <title id="solids-diagram-title">Цилиндр, конус и шар</title><desc id="solids-diagram-desc">Три круглых тела и их основные размеры.</desc>
        <ellipse class="geometry-fill" cx="86" cy="62" rx="47" ry="15"></ellipse><path class="geometry-shape" d="M39 62 L39 177 M133 62 L133 177 M39 62 A47 15 0 0 0 133 62 M39 62 A47 15 0 0 1 133 62 M39 177 A47 15 0 0 0 133 177 M39 177 A47 15 0 0 1 133 177"></path>
        <path class="geometry-fill warm" d="M209 49 L160 177 A49 15 0 0 0 258 177 Z"></path><path class="geometry-shape" d="M209 49 L160 177 M209 49 L258 177 M160 177 A49 15 0 0 0 258 177 M160 177 A49 15 0 0 1 258 177"></path>
        <circle class="geometry-fill" cx="340" cy="120" r="62"></circle><circle class="geometry-shape" cx="340" cy="120" r="62"></circle><ellipse class="geometry-guide dashed" cx="340" cy="120" rx="62" ry="18"></ellipse>
        <text class="diagram-answer" x="59" y="218">цилиндр</text><text class="diagram-answer" x="187" y="218">конус</text><text class="diagram-answer" x="326" y="218">шар</text>
      </svg><figcaption>У цилиндра и конуса одно круглое основание в формуле; коэффициент 1/3 есть только у конуса.</figcaption>
    </figure>`;
  }
  if (type === "probability-outcomes") {
    return `<figure class="theory-diagram probability-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="outcomes-diagram-title outcomes-diagram-desc">
        <title id="outcomes-diagram-title">Благоприятные и все исходы</title><desc id="outcomes-diagram-desc">Семь синих и три зелёных шара образуют десять равновероятных исходов.</desc>
        <g class="probability-outcome good"><circle cx="65" cy="72" r="20"></circle><circle cx="125" cy="72" r="20"></circle><circle cx="185" cy="72" r="20"></circle><circle cx="245" cy="72" r="20"></circle><circle cx="305" cy="72" r="20"></circle><circle cx="95" cy="126" r="20"></circle><circle cx="155" cy="126" r="20"></circle></g>
        <g class="probability-outcome other"><circle cx="215" cy="126" r="20"></circle><circle cx="275" cy="126" r="20"></circle><circle cx="335" cy="126" r="20"></circle></g>
        <text class="diagram-formula" x="112" y="196">P = 7 / 10 = 0,7</text>
      </svg><figcaption>Каждый шар — один равновероятный исход; нужные исходы выделены цветом.</figcaption>
    </figure>`;
  }
  if (type === "probability-complement") {
    return `<figure class="theory-diagram probability-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="complement-diagram-title complement-diagram-desc">
        <title id="complement-diagram-title">Событие и его дополнение</title><desc id="complement-diagram-desc">Событие A и противоположное ему событие вместе дают вероятность один.</desc>
        <rect class="probability-block good" x="54" y="73" width="116" height="86" rx="12"></rect><rect class="probability-block other" x="170" y="73" width="196" height="86" rx="12"></rect>
        <text class="diagram-answer" x="100" y="123">A</text><text class="diagram-answer" x="241" y="123">не A</text>
        <text class="diagram-formula" x="101" y="202">P(A) + P(не A) = 1</text>
      </svg><figcaption>Противоположное событие заполняет всю оставшуюся часть вероятностного пространства.</figcaption>
    </figure>`;
  }
  if (type === "probability-product") {
    return `<figure class="theory-diagram probability-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="product-diagram-title product-diagram-desc">
        <title id="product-diagram-title">Последовательность независимых событий</title><desc id="product-diagram-desc">От события A к событию B ведёт одна ветка, вероятности вдоль неё перемножаются.</desc>
        <circle class="probability-node" cx="62" cy="120" r="15"></circle><circle class="probability-node good" cx="196" cy="78" r="19"></circle><circle class="probability-node good" cx="346" cy="78" r="19"></circle>
        <line class="probability-branch" x1="77" y1="115" x2="177" y2="84"></line><line class="probability-branch" x1="215" y1="78" x2="327" y2="78"></line>
        <text x="111" y="87">P(A)</text><text x="254" y="65">P(B)</text><text class="diagram-answer" x="184" y="84">A</text><text class="diagram-answer" x="334" y="84">B</text>
        <text class="diagram-formula" x="99" y="194">P(A и B) = P(A) · P(B)</text>
      </svg><figcaption>Если нужны оба независимых события, идём по одной ветке и перемножаем.</figcaption>
    </figure>`;
  }
  if (type === "probability-union") {
    return `<figure class="theory-diagram probability-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="union-diagram-title union-diagram-desc">
        <title id="union-diagram-title">Объединение двух событий</title><desc id="union-diagram-desc">Два круга событий пересекаются, общую область нельзя считать дважды.</desc>
        <circle class="probability-set good" cx="174" cy="109" r="72"></circle><circle class="probability-set other" cx="246" cy="109" r="72"></circle>
        <text class="diagram-answer" x="128" y="111">A</text><text class="diagram-answer" x="277" y="111">B</text><text x="192" y="111">A ∩ B</text>
        <text class="diagram-formula" x="50" y="210">P(A ∪ B) = P(A) + P(B) − P(A ∩ B)</text>
      </svg><figcaption>Пересечение принадлежит обоим событиям, поэтому после сложения его вычитают один раз.</figcaption>
    </figure>`;
  }
  if (type === "probability-tree") {
    return `<figure class="theory-diagram probability-diagram">
      <svg viewBox="0 0 420 240" role="img" aria-labelledby="tree-diagram-title tree-diagram-desc">
        <title id="tree-diagram-title">Дерево полной вероятности</title><desc id="tree-diagram-desc">От корня идут ветви A и B, каждая делится на успех и неуспех.</desc>
        <circle class="probability-node" cx="48" cy="120" r="13"></circle>
        <line class="probability-branch" x1="61" y1="115" x2="176" y2="67"></line><line class="probability-branch other" x1="61" y1="125" x2="176" y2="173"></line>
        <line class="probability-branch" x1="194" y1="67" x2="340" y2="43"></line><line class="probability-branch other" x1="194" y1="67" x2="340" y2="91"></line>
        <line class="probability-branch" x1="194" y1="173" x2="340" y2="149"></line><line class="probability-branch other" x1="194" y1="173" x2="340" y2="197"></line>
        <circle class="probability-node good" cx="185" cy="67" r="12"></circle><circle class="probability-node other" cx="185" cy="173" r="12"></circle>
        <text class="diagram-answer" x="111" y="77">A</text><text class="diagram-answer" x="111" y="178">B</text><text x="348" y="47">успех</text><text x="348" y="95">нет</text><text x="348" y="153">успех</text><text x="348" y="201">нет</text>
      </svg><figcaption>Вдоль ветки умножаем, затем складываем все ветки, которые приводят к нужному результату.</figcaption>
    </figure>`;
  }
  return "";
}

function renderTheoryExample(example, secondary = false) {
  if (!example) return "";
  return `<aside class="worked-example ${secondary ? "secondary" : ""}">
    <span>${escapeHtml(example.label)}</span><b>${escapeHtml(example.prompt)}</b>
    <p>${escapeHtml(example.solution)}</p><strong>${escapeHtml(example.answer)}</strong>
  </aside>`;
}

function aiReady() {
  return Boolean(state.aiStatus?.configured);
}

function aiExplanationStyleLabel(style) {
  return {
    simple: "простыми словами",
    why: "объяснение причины",
    algorithm: "алгоритм по шагам",
    worked_example: "разбор на примере",
    definition: "точное определение",
  }[style] || "персональное объяснение";
}

function renderAIRequestState(kind, message) {
  return `<div class="ai-request-state ${kind}" role="status">${kind === "loading" ? "Готовлю ответ…" : escapeHtml(message)}</div>`;
}

function renderAISelfCheckFeedback(answer, checkState) {
  if (!checkState) return "";
  if (checkState.correct) {
    return `<div class="ai-self-check-feedback success" role="status"><b>Верно</b><span>${escapeHtml(answer.check_explanation)}</span></div>`;
  }
  if (checkState.revealed) {
    return `<div class="ai-self-check-feedback revealed" role="status"><b>Разберём ответ</b><span>Верный ответ: ${escapeHtml(answer.check_answer)}. ${escapeHtml(answer.check_explanation)}</span></div>`;
  }
  return `<div class="ai-self-check-feedback retry" role="status"><b>Пока не так</b><span>${escapeHtml(answer.check_hint)}</span></div>`;
}

function normalizeAISelfCheckAnswer(value) {
  return String(value)
    .trim()
    .toLocaleLowerCase("ru-RU")
    .replaceAll("ё", "е")
    .replace(/[−–—]/g, "-")
    .replace(/\s+/g, " ")
    .replace(/[.!?]+$/g, "")
    .trim();
}

function isAISelfCheckCorrect(answer, studentAnswer) {
  const accepted = [answer.check_answer, ...(answer.accepted_answers || [])]
    .map(normalizeAISelfCheckAnswer);
  return accepted.includes(normalizeAISelfCheckAnswer(studentAnswer));
}

function renderAITheoryAnswer(answer, answerKey = "") {
  if (!answer) return "";
  const steps = Array.isArray(answer.steps) ? answer.steps : [];
  const checkReady = Boolean(answerKey && answer.check_answer && answer.check_hint && answer.check_explanation);
  const checkState = state.aiTheoryChecks[answerKey];
  const checkResolved = Boolean(checkState?.correct || checkState?.revealed);
  return `<article class="ai-answer">
    <span>${escapeHtml(aiExplanationStyleLabel(answer.explanation_style))}</span><h4>${escapeHtml(answer.title)}</h4>
    ${answer.question ? `<div class="ai-asked-question"><b>Ваш вопрос</b><p>${escapeHtml(answer.question)}</p></div>` : ""}
    <p class="ai-direct-answer">${escapeHtml(answer.explanation)}</p>
    ${answer.key_rule ? `<div class="ai-key-rule"><b>Главное правило</b><p>${escapeHtml(answer.key_rule)}</p></div>` : ""}
    ${steps.length ? `<ol class="ai-explanation-steps">${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>` : ""}
    <div class="ai-example"><b>Разберём на новых числах</b><p>${escapeHtml(answer.example)}</p></div>
    ${answer.common_mistake ? `<div class="ai-common-mistake"><b>Не перепутайте</b><p>${escapeHtml(answer.common_mistake)}</p></div>` : ""}
    <div class="ai-self-check"><b>Проверь себя</b><p>${escapeHtml(answer.check_question)}</p>
      ${checkReady ? `<form class="ai-self-check-form" data-ai-check-key="${escapeHtml(answerKey)}">
        <input name="answer" maxlength="160" autocomplete="off" placeholder="Введите свой ответ" aria-label="Ответ на вопрос для самопроверки" required ${checkResolved ? "disabled" : ""}>
        <button class="secondary-button" type="submit" ${checkResolved ? "disabled" : ""}>${checkResolved ? "Проверено" : "Проверить"}</button>
      </form>${renderAISelfCheckFeedback(answer, checkState)}` : ""}
    </div>
  </article>`;
}

function renderAITheoryPanel(lesson) {
  const section = lesson.theory.sections?.[state.lessonTheoryPage];
  if (!section) return "";
  const answerKey = `${escapeHtml(lesson.unit_id)}:${section.id}`;
  const answer = state.aiTheoryAnswers[answerKey];
  const disabled = aiReady() ? "" : "disabled";
  if (!aiReady()) return "";
  return `<section class="ai-tutor-card theory-ai-card">
    <header><h3>ИИ-репетитор</h3></header>
    <form class="ai-question-form" id="ai-theory-form">
      <label for="ai-theory-question">Что осталось непонятно?</label>
      <div><input id="ai-theory-question" name="question" maxlength="500" placeholder="Например: объясни проще и приведи другой пример" ${disabled}><button class="secondary-button" type="submit" ${disabled}>Объяснить</button></div>
    </form>
    <div class="ai-response-slot" id="ai-theory-response" aria-live="polite">${renderAITheoryAnswer(answer, answerKey)}</div>
  </section>`;
}

async function requestAITheoryExplanation(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  const section = state.lesson.theory.sections[state.lessonTheoryPage];
  const answerKey = `${state.lesson.unit_id}:${section.id}`;
  const question = new FormData(form).get("question")?.trim() || "Объясни этот раздел проще и проверь, понял ли я его.";
  const responseSlot = document.querySelector("#ai-theory-response");
  delete state.aiTheoryAnswers[answerKey];
  delete state.aiTheoryChecks[answerKey];
  responseSlot.innerHTML = renderAIRequestState(
    "loading",
    "Отвечаю именно на этот вопрос; обычно это занимает несколько секунд.",
  );
  button.disabled = true;
  button.textContent = "Объясняю…";
  try {
    const answer = await aiRequest("/explain-theory", {
      method: "POST",
      body: JSON.stringify({
        lesson_unit_id: state.lesson.unit_id,
        theory_section_id: section.id,
        question,
      }),
    });
    state.aiTheoryAnswers[answerKey] = answer;
    if (!responseSlot.isConnected) return;
    responseSlot.innerHTML = renderAITheoryAnswer(answer, answerKey);
    bindAISelfCheckForms();
  } catch (error) {
    responseSlot.innerHTML = renderAIRequestState("error", error.message);
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Объяснить";
  }
}

function submitAISelfCheck(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const answerKey = form.dataset.aiCheckKey;
  const answer = state.aiTheoryAnswers[answerKey];
  const input = form.elements.answer;
  const studentAnswer = input.value.trim();
  if (!answer || !studentAnswer) return;

  const previousAttempts = state.aiTheoryChecks[answerKey]?.attempts || 0;
  const attempts = previousAttempts + 1;
  const correct = isAISelfCheckCorrect(answer, studentAnswer);
  const revealed = !correct && attempts >= 2;
  state.aiTheoryChecks[answerKey] = { attempts, correct, revealed };

  const check = form.closest(".ai-self-check");
  check.querySelector(".ai-self-check-feedback")?.remove();
  check.insertAdjacentHTML(
    "beforeend",
    renderAISelfCheckFeedback(answer, state.aiTheoryChecks[answerKey]),
  );
  if (correct || revealed) {
    input.disabled = true;
    form.querySelector("button").disabled = true;
    form.querySelector("button").textContent = "Проверено";
  } else {
    input.select();
  }
}

function bindAISelfCheckForms() {
  document.querySelectorAll(".ai-self-check-form").forEach((form) => {
    form.addEventListener("submit", submitAISelfCheck);
  });
}

function bindAITheoryControls() {
  document.querySelector("#ai-theory-form")?.addEventListener("submit", requestAITheoryExplanation);
  bindAISelfCheckForms();
}

function renderAIHintItems(hints) {
  if (!hints.length) return "";
  return hints.map((hint) => `<article class="ai-hint-item"><span>Подсказка ${escapeHtml(hint.level)}</span><b>${escapeHtml(hint.focus)}</b><p>${escapeHtml(hint.hint)}</p><small>${escapeHtml(hint.self_check)}</small></article>`).join("");
}

function renderAIHintPanel(lesson) {
  if (!aiReady()) return "";
  const taskKey = lesson.practice_task.lesson_task_key;
  const hints = state.aiHints[taskKey] || [];
  const nextLevel = hints.length + 1;
  const disabled = !aiReady() || nextLevel > 3;
  const buttonLabel = !aiReady() ? "Подсказки временно недоступны" : nextLevel > 3 ? "Все подсказки получены" : `Подсказка ${nextLevel} из 3`;
  return `<section class="ai-hint-control">
    <div class="ai-hint-list" id="ai-hint-list">${renderAIHintItems(hints)}</div>
    <button class="secondary-button ai-hint-button" id="ai-hint-button" type="button" ${disabled ? "disabled" : ""}>${buttonLabel}</button>
  </section>`;
}

async function requestAIHint() {
  const task = state.lesson.practice_task;
  const hints = state.aiHints[task.lesson_task_key] || [];
  const level = hints.length + 1;
  if (level > 3) return;
  const button = document.querySelector("#ai-hint-button");
  button.disabled = true;
  button.textContent = "Готовлю подсказку…";
  try {
    const hint = await aiRequest("/hint", {
      method: "POST",
      body: JSON.stringify({
        lesson_unit_id: state.lesson.unit_id,
        lesson_task_key: task.lesson_task_key,
        level,
      }),
    });
    state.aiHints[task.lesson_task_key] = [...hints, hint];
    if (!button.isConnected) return;
    document.querySelector("#ai-hint-list").innerHTML = renderAIHintItems(state.aiHints[task.lesson_task_key]);
    const nextLevel = level + 1;
    button.textContent = nextLevel > 3 ? "Все подсказки получены" : `Подсказка ${nextLevel} из 3`;
    button.disabled = nextLevel > 3;
  } catch (error) {
    button.disabled = false;
    button.textContent = `Подсказка ${level} из 3`;
    toast(error.message);
  }
}

function bindAIHintControls() {
  document.querySelector("#ai-hint-button")?.addEventListener("click", requestAIHint);
}

function renderAIErrorAnswer(answer) {
  if (!answer) return "";
  return `<article class="ai-error-answer">
    <h4>${escapeHtml(answer.diagnosis)}</h4>
    <dl><div><dt>На чём основан вывод</dt><dd>${escapeHtml(answer.evidence)}</dd></div><div><dt>Почему возникла ошибка</dt><dd>${escapeHtml(answer.explanation)}</dd></div><div><dt>Короткий микроурок</dt><dd>${escapeHtml(answer.micro_lesson)}</dd></div><div><dt>Следующее действие</dt><dd>${escapeHtml(answer.next_action)}</dd></div></dl>
    <small>${escapeHtml(answer.confidence_note)}</small>
  </article>`;
}

function renderAIErrorAction(attemptId) {
  if (!aiReady()) return "";
  const disabled = aiReady() ? "" : "disabled";
  return `<section class="ai-error-control">
    <button class="secondary-button" type="button" data-ai-error="${escapeHtml(attemptId)}" ${disabled}>${aiReady() ? "Разобрать с ИИ" : "ИИ-разбор временно недоступен"}</button>
    <div class="ai-response-slot" id="ai-error-response" aria-live="polite"></div>
  </section>`;
}

async function requestAIErrorAnalysis(event) {
  const button = event.currentTarget;
  const attemptId = button.dataset.aiError;
  button.disabled = true;
  button.textContent = "Анализирую…";
  try {
    const answer = await aiRequest("/analyze-error", {
      method: "POST",
      body: JSON.stringify({ attempt_id: attemptId }),
    });
    document.querySelector("#ai-error-response").innerHTML = renderAIErrorAnswer(answer);
    button.textContent = "Разбор готов";
  } catch (error) {
    button.disabled = false;
    button.textContent = "Разобрать с ИИ";
    toast(error.message);
  }
}

function bindAIErrorAnalysis() {
  document.querySelector("[data-ai-error]")?.addEventListener("click", requestAIErrorAnalysis);
}

function renderDetailedTheory(chapter) {
  const scope = chapter.exam_scope;
  const lastPage = chapter.sections.length - 1;
  const pageIndex = Math.min(Math.max(state.lessonTheoryPage, 0), lastPage);
  const section = chapter.sections[pageIndex];
  const introduction = pageIndex === 0 ? `<details class="exam-scope"><summary>${escapeHtml(scope.label)}</summary><p>${escapeHtml(scope.text)}</p><ul>${scope.skills.map((skill) => `<li>${escapeHtml(skill)}</li>`).join("")}</ul></details>` : "";
  const review = pageIndex === lastPage ? `<section class="exam-pattern-section"><h3>Как узнать тип задания</h3>
      <div class="exam-pattern-grid">${chapter.exam_patterns.map((pattern, index) => `<article><span>0${index + 1}</span><b>${escapeHtml(pattern.title)}</b><p>${escapeHtml(pattern.method)}</p></article>`).join("")}</div>
    </section>
    <div class="theory-review-grid">
      <section class="mistake-card"><h3>Где теряют балл</h3><ul>${chapter.mistakes.map((mistake) => `<li>${escapeHtml(mistake)}</li>`).join("")}</ul></section>
      <section class="checklist-card"><h3>Проверка ответа</h3><ol>${chapter.checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol></section>
    </div>
    <footer class="theory-reference"><b>Основа конспекта</b><span>${escapeHtml(chapter.reference.title)} · ${escapeHtml(chapter.reference.sections)}</span><small>${escapeHtml(chapter.reference.note)}</small></footer>` : "";

  return `<div class="theory-page-status">
      <div><span>Теория</span><b>Страница ${pageIndex + 1} из ${escapeHtml(chapter.sections.length)}</b></div>
    </div>
    ${introduction}
    <div class="detailed-theory"><section class="theory-section" id="theory-section-${escapeHtml(section.id)}">
      <header><span>${escapeHtml(section.number)}</span><div><h3>${escapeHtml(section.title)}</h3></div></header>
      <div class="theory-section-layout ${section.diagram ? "with-diagram" : ""}">
        <div class="theory-section-copy"><p class="section-lead">${escapeHtml(section.lead)}</p>
          <ul class="explanation-list">${section.paragraphs.map((paragraph) => `<li>${escapeHtml(paragraph)}</li>`).join("")}</ul>
          <div class="section-formulas">${section.formulas.map((formula) => `<code>${escapeHtml(formula)}</code>`).join("")}</div>
        </div>
        ${theoryDiagram(section.diagram)}
      </div>
      <div class="example-row">${renderTheoryExample(section.example)}${renderTheoryExample(section.secondary_example, true)}</div>
      <p class="exam-note"><b>На ЕГЭ</b>${escapeHtml(section.exam_note)}</p>
    </section></div>
    ${review}`;
}

function renderLessonTheory(chapter) {
  if (chapter.sections?.length) return renderDetailedTheory(chapter);
  return `<ul class="formula-list">${chapter.key_points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>`;
}

function renderCompletedTheorySection(section) {
  return `<section class="theory-section" id="completed-theory-section-${escapeHtml(section.id)}">
    <header><span>${escapeHtml(section.number)}</span><div><h3>${escapeHtml(section.title)}</h3></div></header>
    <div class="theory-section-layout ${section.diagram ? "with-diagram" : ""}">
      <div class="theory-section-copy"><p class="section-lead">${escapeHtml(section.lead)}</p>
        <ul class="explanation-list">${section.paragraphs.map((paragraph) => `<li>${escapeHtml(paragraph)}</li>`).join("")}</ul>
        <div class="section-formulas">${section.formulas.map((formula) => `<code>${escapeHtml(formula)}</code>`).join("")}</div>
      </div>
      ${theoryDiagram(section.diagram)}
    </div>
    <div class="example-row">${renderTheoryExample(section.example)}${renderTheoryExample(section.secondary_example, true)}</div>
    <p class="exam-note"><b>На ЕГЭ</b>${escapeHtml(section.exam_note)}</p>
  </section>`;
}

function renderCompletedTheoryContent(chapter) {
  const scope = chapter.exam_scope
    ? `<details class="exam-scope"><summary>${escapeHtml(chapter.exam_scope.label)}</summary><p>${escapeHtml(chapter.exam_scope.text)}</p><ul>${chapter.exam_scope.skills.map((skill) => `<li>${escapeHtml(skill)}</li>`).join("")}</ul></details>`
    : "";
  const lessonBlocks = chapter.sections?.length
    ? `<div class="detailed-theory completed-theory-blocks">${chapter.sections.map(renderCompletedTheorySection).join("")}</div>`
    : `<section class="completed-theory-key-points"><p class="eyebrow">Ключевые правила урока</p><ul class="formula-list">${chapter.key_points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul></section>`;
  const patterns = chapter.exam_patterns?.length
    ? `<section class="exam-pattern-section"><h3>Как узнать тип задания</h3><div class="exam-pattern-grid">${chapter.exam_patterns.map((pattern, index) => `<article><span>${String(index + 1).padStart(2, "0")}</span><b>${escapeHtml(pattern.title)}</b><p>${escapeHtml(pattern.method)}</p></article>`).join("")}</div></section>`
    : "";
  const review = chapter.mistakes?.length && chapter.checklist?.length
    ? `<div class="theory-review-grid"><section class="mistake-card"><h3>Где теряют балл</h3><ul>${chapter.mistakes.map((mistake) => `<li>${escapeHtml(mistake)}</li>`).join("")}</ul></section><section class="checklist-card"><h3>Проверка ответа</h3><ol>${chapter.checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol></section></div>`
    : "";
  const reference = chapter.reference
    ? `<footer class="theory-reference"><b>Основа конспекта</b><span>${escapeHtml(chapter.reference.title)} · ${escapeHtml(chapter.reference.sections)}</span><small>${escapeHtml(chapter.reference.note)}</small></footer>`
    : "";
  return `${scope}${lessonBlocks}${patterns}${review}${reference}<aside class="theory-tip"><b>Совет для повторения</b>${escapeHtml(chapter.tip)}</aside>`;
}

function renderCompletedTheoryCard(item) {
  const chapter = item.theory;
  return `<article class="completed-theory-chapter" id="completed-theory-${escapeHtml(chapter.id)}">
    <header class="completed-theory-heading">
      <span class="completed-theory-position">${String(item.position).padStart(2, "0")}</span>
      <div class="completed-theory-title"><h2>${escapeHtml(chapter.title)}</h2><p>${escapeHtml(chapter.summary)}</p></div>
    </header>
    <div class="completed-theory-content">${renderCompletedTheoryContent(chapter)}</div>
  </article>`;
}

function renderTheoryActions(chapter, reviewingTheory, lesson) {
  const returnLabel = "Вернуться к практике →";
  const completedLabel = `Выполнено ${escapeHtml(lesson.practice.attempted_tasks)} из ${escapeHtml(lesson.practice.total_tasks)} задач`;
  if (!chapter.sections?.length) {
    return `<div class="lesson-action"><span>${reviewingTheory ? completedLabel : `${escapeHtml(chapter.read_minutes)} минут на изучение`}</span><button class="primary-button" ${reviewingTheory ? "data-return-practice" : 'id="complete-theory"'}>${reviewingTheory ? returnLabel : "Перейти к практике →"}</button></div>`;
  }

  const pageIndex = state.lessonTheoryPage;
  const lastPage = chapter.sections.length - 1;
  return `<div class="theory-page-actions">
      <button class="secondary-button" type="button" data-theory-prev ${pageIndex === 0 ? "disabled" : ""}>← Назад</button>
      ${pageIndex < lastPage
        ? `<button class="primary-button" type="button" data-theory-next>Следующая страница →</button>`
        : `<button class="primary-button" type="button" ${reviewingTheory ? "data-return-practice" : 'id="complete-theory"'}>${reviewingTheory ? returnLabel : "Перейти к практике →"}</button>`}
    </div>`;
}

function syncTheoryPages(lesson) {
  if (!lesson.theory?.sections?.length) return;
  if (state.lessonTheoryUnitId === lesson.unit_id) return;
  state.lessonTheoryUnitId = lesson.unit_id;
  state.lessonTheoryPage = 0;
}

function openTheoryPage(pageIndex) {
  const lastPage = state.lesson.theory.sections.length - 1;
  const target = Math.min(Math.max(pageIndex, 0), lastPage);
  state.lessonTheoryPage = target;
  renderLessons();
  view.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: scrollBehavior() });
}

function bindTheoryPageControls() {
  document.querySelector("[data-theory-prev]")?.addEventListener("click", () => openTheoryPage(state.lessonTheoryPage - 1));
  document.querySelector("[data-theory-next]")?.addEventListener("click", () => openTheoryPage(state.lessonTheoryPage + 1));
}

function renderLearningTask(task, formId, inputId, buttonLabel) {
  return `<div class="task-meta"><span class="tag accent">Задание ${escapeHtml(task.exam_number)}</span><span class="tag">${difficultyLabel(task.difficulty)}</span></div>
    <h2>${escapeHtml(task.title)}</h2><p class="task-prompt">${escapeHtml(task.prompt)}</p>
    <form class="answer-block" id="${formId}"><label for="${inputId}">Ваш ответ</label><div class="answer-row">
      <input id="${inputId}" name="answer" maxlength="500" autocomplete="off" placeholder="Введите ответ" required>
      <button class="primary-button" type="submit">${buttonLabel}</button></div></form>
    <div id="feedback-slot" role="status" aria-live="polite" tabindex="-1"></div>
    <p class="task-source">Учебное задание · <a href="${safeUrl(task.source.url)}" target="_blank" rel="noreferrer">${escapeHtml(task.source.label)}</a></p>`;
}

function renderPracticeStep(lesson) {
  const task = lesson.practice_task;
  return `<article class="lesson-panel lesson-task">
    <div class="practice-toolbar"><div><span>Задача ${escapeHtml(lesson.practice.current_task_number)} из ${escapeHtml(lesson.practice.total_tasks)}</span><i><b style="width:${lesson.practice.attempted_tasks / lesson.practice.total_tasks * 100}%"></b></i></div><button class="secondary-button" id="review-theory">← Вернуться к теории</button></div>
    <div class="task-meta"><span class="tag accent">Задание ${escapeHtml(task.exam_number)}</span><span class="tag">${difficultyLabel(task.difficulty)}</span></div>
    ${task.title === lesson.topic.short_title ? "" : `<h2>${escapeHtml(task.title)}</h2>`}<p class="task-prompt">${escapeHtml(task.prompt)}</p>
    ${renderAIHintPanel(lesson)}
    <form class="answer-block" id="lesson-answer-form"><label for="lesson-answer">Ваш ответ</label><div class="answer-row">
      <input id="lesson-answer" name="answer" maxlength="500" autocomplete="off" placeholder="Введите ответ" required>
      <button class="primary-button" type="submit">Проверить</button></div></form>
    <div id="feedback-slot" role="status" aria-live="polite" tabindex="-1"></div>
    <p class="task-source">Учебное задание · <a href="${safeUrl(task.source.url)}" target="_blank" rel="noreferrer">${escapeHtml(task.source.label)}</a></p>
  </article>`;
}

function renderLessons() {
  const lesson = state.lesson;
  if (lesson.status === "completed") {
    view.innerHTML = `${pageHeader("Учебный маршрут завершён", "")}
      <section class="lesson-complete"><span>✓</span><h2>Отличная работа</h2><p>Вы завершили ${escapeHtml(lesson.total_units)} уроков. Назначенные самостоятельные работы остаются в отдельном разделе.</p><div class="complete-actions"><button class="secondary-button" data-go="roadmap">Посмотреть роадмап</button><button class="primary-button" data-go="homework">Домашние задания →</button></div></section>`;
    bindGoButtons();
    return;
  }

  syncTheoryPages(lesson);

  const currentStep = lesson.current_step;
  const reviewingTheory = currentStep === "practice" && state.lessonView === "theory";
  const isTheory = currentStep === "theory" || reviewingTheory;
  let stepContent;
  if (isTheory) {
    const returnText = "Вернуться к задаче →";
    stepContent = `<article class="lesson-panel lesson-theory">
      ${reviewingTheory ? `<div class="review-theory-banner"><b>Повторение теории</b><button class="secondary-button" type="button" data-return-practice>${returnText}</button></div>` : ""}
      ${renderLessonTheory(lesson.theory)}
      ${renderAITheoryPanel(lesson)}
      ${!lesson.theory.sections?.length || state.lessonTheoryPage === lesson.theory.sections.length - 1 ? `<aside class="theory-tip"><b>Совет перед практикой</b>${escapeHtml(lesson.theory.tip)}</aside>` : ""}
      ${renderTheoryActions(lesson.theory, reviewingTheory, lesson)}
    </article>`;
  } else {
    stepContent = renderPracticeStep(lesson);
  }

  view.innerHTML = `${pageHeader(lesson.topic.short_title, `Тема ${lesson.position} из ${lesson.total_units}`)}
    <section class="lesson-shell">
      <ol class="lesson-stepper">${lesson.steps.map((step, index) => `<li class="lesson-step ${escapeHtml(step.state)}" ${step.state === "current" ? 'aria-current="step"' : ""}><span>${step.state === "completed" ? "✓" : index + 1}</span><div><b>${escapeHtml(step.label)}</b></div></li>`).join("")}</ol>
      ${stepContent}
    </section>`;
  bindGoButtons();
  if (isTheory) {
    bindTheoryPageControls();
    bindAITheoryControls();
  }
  if (currentStep === "theory") {
    document.querySelector("#complete-theory")?.addEventListener("click", completeCurrentTheory);
  } else if (reviewingTheory) {
    document.querySelectorAll("[data-return-practice]").forEach((button) => button.addEventListener("click", returnToPractice));
  } else if (currentStep === "practice") {
    document.querySelector("#review-theory")?.addEventListener("click", reviewCurrentTheory);
    bindAIHintControls();
    document.querySelector("#lesson-answer-form")?.addEventListener("submit", submitLessonAnswer);
  }
}

function renderHomework() {
  const homework = state.homework;
  if (homework.status !== "active") {
    view.innerHTML = `${pageHeader("Домашние задания", "", '<button class="secondary-button" data-go="lessons">Перейти к урокам</button>')}
      <section class="homework-empty"><h2>Нет назначенных заданий</h2></section>`;
    bindGoButtons();
    return;
  }
  const task = homework.task;
  view.innerHTML = `${pageHeader(homework.topic.short_title, `Сдать до ${formatDate(homework.due_date)}`, '<button class="secondary-button" data-go="lessons">К урокам</button>')}
    <section class="homework-shell">
      <article class="lesson-panel lesson-task homework-workspace">
        <div class="practice-toolbar homework-progress"><div><span>Задача ${escapeHtml(homework.current_task_number)} из ${escapeHtml(homework.total_tasks)}</span><i><b style="width:${homework.attempted_tasks / homework.total_tasks * 100}%"></b></i></div></div>
        <div class="task-meta"><span class="tag accent">Задание ${escapeHtml(task.exam_number)}</span><span class="tag">${difficultyLabel(task.difficulty)}</span></div>
        ${task.title === homework.topic.short_title ? "" : `<h2>${escapeHtml(task.title)}</h2>`}<p class="task-prompt">${escapeHtml(task.prompt)}</p>
        <form class="answer-block" id="homework-answer-form"><label for="homework-answer">Ваш ответ</label><div class="answer-row">
          <input id="homework-answer" name="answer" maxlength="500" autocomplete="off" placeholder="Введите ответ" required>
          <button class="primary-button" type="submit">Сдать работу</button></div></form>
        <div id="feedback-slot" role="status" aria-live="polite" tabindex="-1"></div>
        <p class="task-source">Учебное задание · <a href="${safeUrl(task.source.url)}" target="_blank" rel="noreferrer">${escapeHtml(task.source.label)}</a></p>
      </article>
    </section>`;
  bindGoButtons();
  document.querySelector("#homework-answer-form").addEventListener("submit", submitHomeworkAnswer);
}

async function refreshLearningData() {
  const generation = state.auth.generation;
  const [completedTheory, analytics, roadmap, lesson, homework, dashboard] = await Promise.all([
    request(`/theory/completed`),
    request(`/analytics`), request(`/roadmap`),
    request(`/lesson/current`),
    request(`/homework/current`),
    request(`/dashboard`),
  ]);
  assertCurrentSession(generation);
  Object.assign(state, { completedTheory, analytics, roadmap, lesson, homework, dashboard });
  if (state.role === "admin") {
    const [admin, adminUsers] = await Promise.all([
      request("/admin/dashboard"), request("/admin/users"),
    ]);
    assertCurrentSession(generation);
    Object.assign(state, { admin, adminUsers });
  }
  updateHomeworkBadge();
}

async function syncSavedLearningData() {
  try { await refreshLearningData(); }
  catch (error) {
    if (error.silent) throw error;
    toast("Изменение сохранено, но сводку обновить не удалось. Перезагрузите страницу для обновления.");
  }
}

function reviewCurrentTheory() {
  state.lessonView = "theory";
  state.lessonTheoryPage = 0;
  renderLessons();
}

function returnToPractice() {
  state.lessonView = null;
  renderLessons();
}

async function completeCurrentTheory() {
  if (state.lesson.theory.sections?.length && state.lessonTheoryPage !== state.lesson.theory.sections.length - 1) {
    toast("Сначала пройдите все страницы теории.");
    return;
  }
  const button = document.querySelector("#complete-theory");
  button.disabled = true;
  button.textContent = "Сохраняем…";
  try {
    state.lesson = await request("/lesson/theory/complete", {
      method: "POST",
      body: JSON.stringify({ lesson_unit_id: state.lesson.unit_id }),
    });
    await syncSavedLearningData();
    state.lessonView = null;
    state.lessonTheoryPage = 0;
    if (button.isConnected) { renderLessons(); view.focus({ preventScroll: true }); }
    toast("Теория пройдена. Открыта практика.");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Перейти к практике →";
    toast(error.message);
  }
}

async function submitLessonAnswer(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  const answer = new FormData(form).get("answer");
  const mode = "practice";
  const task = state.lesson.practice_task;
  const practiceTopic = state.lesson.topic.short_title;
  const practiceNumber = state.lesson.practice.current_task_number;
  const practiceTotal = state.lesson.practice.total_tasks;
  button.disabled = true;
  button.textContent = "Проверяем…";
  try {
    const result = await request("/attempts", {
      method: "POST",
      body: JSON.stringify({
        task_id: task.id,
        answer,
        duration_seconds: 90,
        mode,
        lesson_unit_id: state.lesson.unit_id,
        lesson_task_key: task.lesson_task_key,
      }),
    });
    state.lesson = result.lesson;
    state.homework = result.homework;
    await syncSavedLearningData();
    state.lessonView = null;
    const correctTitle = result.practice_complete
      ? `Практика «${escapeHtml(practiceTopic)}» завершена`
      : `Верно — задача ${practiceNumber} из ${practiceTotal}`;
    const incorrectTitle = `Неверно — задача ${practiceNumber} из ${practiceTotal} завершена`;
    if (!form.isConnected) return;
    document.querySelector("#feedback-slot").innerHTML = `<div class="feedback ${result.is_correct ? "correct" : "incorrect"}">
      <b>${result.is_correct ? correctTitle : incorrectTitle}</b>
      ${result.is_correct ? "" : `Верный ответ: ${escapeHtml(result.correct_answer)}.<br>`}${escapeHtml(result.explanation)}
      ${result.is_correct ? "" : renderAIErrorAction(result.attempt.id)}
      <div class="feedback-action"><button class="primary-button" id="lesson-next">${result.practice_complete ? "Перейти к следующему уроку" : "Следующая задача"} →</button>${result.practice_complete ? '<button class="secondary-button" id="lesson-homework">Открыть ДЗ</button>' : ""}</div>
    </div>`;
    form.classList.add("hidden");
    document.querySelector("#ai-hint-button")?.classList.add("hidden");
    document.querySelector("#feedback-slot").focus({ preventScroll: true });
    if (!result.is_correct) bindAIErrorAnalysis();
    document.querySelector("#lesson-next").addEventListener("click", () => { renderLessons(); view.focus(); });
    document.querySelector("#lesson-homework")?.addEventListener("click", () => goTo("homework"));
  } catch (error) {
    toast(error.message);
  } finally {
    if (!form.classList.contains("hidden")) {
      button.disabled = false;
      button.textContent = "Проверить";
    }
  }
}

async function submitHomeworkAnswer(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  const answer = new FormData(form).get("answer");
  const assignment = state.homework;
  const homeworkNumber = assignment.current_task_number;
  const homeworkTotal = assignment.total_tasks;
  button.disabled = true;
  button.textContent = "Проверяем…";
  try {
    const result = await request("/attempts", {
      method: "POST",
      body: JSON.stringify({
        task_id: assignment.task.id,
        answer,
        duration_seconds: 120,
        mode: "homework",
        lesson_unit_id: assignment.unit_id,
        lesson_task_key: assignment.task.lesson_task_key,
      }),
    });
    await syncSavedLearningData();
    const title = result.is_correct
      ? result.homework_unit_complete ? "Домашняя работа завершена" : `Верно — задача ${homeworkNumber} из ${homeworkTotal}`
      : `Неверно — задача ${homeworkNumber} из ${homeworkTotal} завершена`;
    if (!form.isConnected) return;
    document.querySelector("#feedback-slot").innerHTML = `<div class="feedback ${result.is_correct ? "correct" : "incorrect"}">
      <b>${title}</b>
      ${result.is_correct ? "" : `Верный ответ: ${escapeHtml(result.correct_answer)}.<br>`}${escapeHtml(result.explanation)}
      ${result.is_correct ? "" : renderAIErrorAction(result.attempt.id)}
      <div class="feedback-action"><button class="primary-button" id="homework-next">${result.homework_unit_complete ? "Готово" : "Следующая задача"} →</button></div>
    </div>`;
    form.classList.add("hidden");
    document.querySelector("#feedback-slot").focus({ preventScroll: true });
    if (!result.is_correct) bindAIErrorAnalysis();
    document.querySelector("#homework-next").addEventListener("click", () => {
      if (state.homework.status === "active") { renderHomework(); view.focus(); }
      else goTo("dashboard");
    });
  } catch (error) {
    toast(error.message);
  } finally {
    if (!form.classList.contains("hidden")) {
      button.disabled = false;
      button.textContent = "Сдать работу";
    }
  }
}

function filteredTasks() {
  return state.practiceFilter === "all" ? state.tasks : state.tasks.filter((task) => task.difficulty === state.practiceFilter);
}

function renderPractice() {
  const list = filteredTasks();
  if (state.currentTask >= list.length) state.currentTask = 0;
  const task = list[state.currentTask];
  view.innerHTML = `${pageHeader("Практика")}
    <div class="practice-layout">
      <aside class="task-sidebar">
        <div class="filter-group"><label>Сложность</label>
          ${[["all", "Все"], ["basic", "База"], ["standard", "Средние"], ["advanced", "Повышенные"], ["expert", "Сложные"]].map(([value, label]) => `<button class="filter-chip ${state.practiceFilter === value ? "active" : ""}" data-filter="${value}">${label}</button>`).join("")}
        </div>
        <div class="filter-group"><label>Номер задания</label><div class="task-numbers">
          ${list.map((item, index) => `<button class="task-number ${index === state.currentTask ? "active" : ""} ${item.difficulty === "expert" ? "complex" : ""}" data-task-index="${index}">${escapeHtml(item.exam_number)}</button>`).join("")}
        </div></div>
      </aside>
      <section class="task-workspace">
        <div class="task-meta"><span class="tag accent">Задание ${escapeHtml(task.exam_number)}</span><span class="tag">${difficultyLabel(task.difficulty)}</span><span class="tag">до ${escapeHtml(task.max_primary_score)} перв. балл.</span></div>
        <h2>${escapeHtml(task.title)}</h2><p class="task-prompt">${escapeHtml(task.prompt)}</p>
        <div class="content-links prominent"><a href="#theory-${escapeHtml(task.theory_id)}" data-open-theory="${escapeHtml(task.theory_id)}">Открыть теорию по теме →</a></div>
        <form class="answer-block" id="answer-form"><label for="answer">Ваш ответ</label><div class="answer-row">
          <input id="answer" name="answer" maxlength="500" autocomplete="off" placeholder="Введите число" required>
          <button class="primary-button" type="submit">Проверить</button></div></form>
        <div id="feedback-slot" role="status" aria-live="polite" tabindex="-1"></div>
        <p class="task-source">Учебное задание · <a href="${safeUrl(task.source.url)}" target="_blank" rel="noreferrer">открытые материалы ФИПИ ЕГЭ-2026</a></p>
        <div class="task-nav"><button class="secondary-button" data-task-step="-1" ${state.currentTask === 0 ? "disabled" : ""}>← Назад</button><button class="secondary-button" data-task-step="1" ${state.currentTask === list.length - 1 ? "disabled" : ""}>Следующее →</button></div>
      </section>
    </div>`;

  document.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", () => {
    state.practiceFilter = button.dataset.filter; state.currentTask = 0; renderPractice();
  }));
  document.querySelectorAll("[data-task-index]").forEach((button) => button.addEventListener("click", () => {
    state.currentTask = Number(button.dataset.taskIndex); renderPractice();
  }));
  document.querySelectorAll("[data-task-step]").forEach((button) => button.addEventListener("click", () => {
    state.currentTask += Number(button.dataset.taskStep); renderPractice();
  }));
  document.querySelector("#answer-form").addEventListener("submit", submitAnswer);
  bindContentLinks();
}

async function submitAnswer(event) {
  event.preventDefault();
  const generation = state.auth.generation;
  const form = event.currentTarget;
  const list = filteredTasks();
  const task = list[state.currentTask];
  const answer = new FormData(event.currentTarget).get("answer");
  const button = event.currentTarget.querySelector("button");
  button.disabled = true; button.textContent = "Проверяем…";
  try {
    const result = await request("/attempts", {
      method: "POST",
      body: JSON.stringify({ task_id: task.id, answer, duration_seconds: 90 }),
    });
    if (!form.isConnected) return;
    document.querySelector("#feedback-slot").innerHTML = `<div class="feedback ${result.is_correct ? "correct" : "incorrect"}">
      <b>${result.is_correct ? "Верно" : `Пока не так. Ответ: ${escapeHtml(result.correct_answer)}`}</b>
      ${escapeHtml(result.explanation)}</div>`;
    const [analytics, roadmap] = await Promise.all([
      request(`/analytics`), request(`/roadmap`),
    ]);
    Object.assign(state, { analytics, roadmap });
    if (state.role === "admin") {
      const [admin, adminUsers] = await Promise.all([
        request("/admin/dashboard"), request("/admin/users"),
      ]);
      assertCurrentSession(generation);
    Object.assign(state, { admin, adminUsers });
    }
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false; button.textContent = "Проверить";
  }
}

function renderTheory() {
  const chapters = state.completedTheory;
  if (!chapters.length) {
    view.innerHTML = `${pageHeader("Пройденная теория", "")}
      <section class="theory-history-empty"><h2>Пока нет пройденных конспектов</h2><p>Они появятся после прохождения теории в уроках.</p><button class="primary-button" data-go="lessons">Перейти к уроку →</button></section>`;
    bindGoButtons();
    return;
  }
  view.innerHTML = `${pageHeader("Пройденная теория", "")}
    <div class="theory-history-list" aria-label="Пройденные теоретические блоки">${chapters.map(renderCompletedTheoryCard).join("")}</div>`;
}

function renderPredictionHistory(history, maxScore) {
  if (!history.length) return "";
  const step = history.length === 1 ? 0 : 504 / (history.length - 1);
  const x = (index) => history.length === 1 ? 280 : 28 + index * step;
  const y = (score) => 218 - score / maxScore * 172;
  const points = history.map((item, index) => `${x(index)},${y(item.score)}`).join(" ");
  const areaPoints = `${x(0)},218 ${points} ${x(history.length - 1)},218`;
  const gridScores = [0, 25, 50, 75, 100];
  return `<svg class="forecast-chart score-history-chart" viewBox="0 0 560 235" role="img" aria-label="Динамика ожидаемого вторичного балла ЕГЭ">
      ${gridScores.map((score) => `<line class="grid" x1="28" y1="${y(score)}" x2="532" y2="${y(score)}"></line><text x="2" y="${y(score) + 4}">${score}</text>`).join("")}
      <polygon class="area" points="${areaPoints}"></polygon><polyline class="line" points="${points}"></polyline>
      ${history.map((item, index) => `<circle class="dot" cx="${x(index)}" cy="${y(item.score)}" r="5"></circle>`).join("")}
    </svg><div class="chart-labels score-chart-labels">${history.map((item) => `<span>${escapeHtml(item.label)}<br><b>${escapeHtml(item.score)} / ${escapeHtml(item.max_score)}</b></span>`).join("")}</div>`;
}

function renderAnalytics() {
  const data = state.analytics;
  const prediction = data.prediction;
  view.innerHTML = `${pageHeader("Аналитика", "")}
    <div class="analytics-grid">
      <article class="metric-card"><small>Попыток</small><b>${escapeHtml(data.summary.attempts)}</b></article>
      <article class="metric-card"><small>Верных</small><b>${escapeHtml(data.summary.correct)}</b></article>
      <article class="metric-card"><small>Типов проверено</small><b>${escapeHtml(prediction.covered_task_types)}<span class="metric-suffix"> / ${escapeHtml(prediction.required_task_types)}</span></b></article>
      <article class="metric-card"><small>Прогноз ЕГЭ</small><b>${prediction.available ? prediction.predicted_test_score : "—"}<span class="metric-suffix"> / ${escapeHtml(prediction.max_test_score)}</span></b>${prediction.available ? "" : `<p class="metric-note">Нужны ответы по всем ${escapeHtml(prediction.required_task_types)} типам</p>`}</article>

      ${data.prediction_history.length ? `<section class="panel chart-panel"><div class="section-heading"><h2>Динамика балла</h2></div>
        ${renderPredictionHistory(data.prediction_history, data.prediction.max_test_score)}
      </section>` : ""}
      <section class="panel mastery-panel"><div class="section-heading"><div><h2>Результаты по темам</h2></div></div>
        <div class="mastery-list">${data.topics.filter((item) => item.attempts > 0).map((item) => `<div class="mastery-item" style="--topic-color:${safeColor(item.accent)}"><div><b>${escapeHtml(item.short_title)}</b><span>${percent(item.mastery)} · ${attemptCount(item.attempts)}</span></div><div class="mini-track"><i style="width:${item.mastery ?? 0}%;background:${safeColor(item.accent)}"></i></div><span class="content-links"><a href="${safeUrl(item.theory_href)}" data-open-theory="${escapeHtml(item.theory_id)}">Теория</a><a href="${safeUrl(item.practice_href)}" data-open-task="${escapeHtml(state.tasks.find((task) => task.topic_id === item.topic_id)?.id || "")}">Практика</a></span></div>`).join("") || '<div class="empty-state compact">Пока нет решений. <button class="secondary-button" data-go="lessons">Перейти к уроку</button></div>'}</div>
      </section>
      ${data.individual_plan.length ? `<section class="panel plan-panel"><div class="section-heading"><div><h2>Повторить</h2></div></div>
        <div class="plan-list">${data.individual_plan.map((item) => `<article class="plan-item"><span><b>${escapeHtml(item.title)}</b><span class="content-links"><a href="${safeUrl(item.theory_href)}" data-open-theory="${escapeHtml(item.theory_id)}">Теория</a><a href="${safeUrl(item.practice_href)}" data-open-task="${escapeHtml(item.task_id)}">Практика</a></span></span><time>${formatDate(item.due_date)}</time></article>`).join("")}</div>
      </section>` : ""}
    </div>`;
  bindContentLinks();
  bindGoButtons();
}

function riskLabel(risk) {
  return { stable: "Стабильно", attention: "Внимание", critical: "Риск" }[risk];
}

function renderAdmin() {
  const admin = state.admin;
  const usersRows = state.adminUsers.length ? state.adminUsers.map((user) => `<tr><td><b>${escapeHtml(user.name)}</b></td><td>${escapeHtml(user.attempts)}</td><td>${escapeHtml(user.accuracy)}%</td><td>${user.primary_result ?? "—"}</td><td>${formatDateTime(user.activity)}</td><td><span class="status-chip ${escapeHtml(user.risk)}">${riskLabel(user.risk)}</span></td></tr>`).join("") : `<tr><td colspan="6"><div class="empty-state compact">Пока нет решений.</div></td></tr>`;
  view.innerHTML = `${pageHeader("Панель управления")}
    <section class="section"><div class="analytics-grid">
      <article class="metric-card"><small>Сессий с решениями</small><b>${escapeHtml(admin.metrics.students)}</b></article>
      <article class="metric-card"><small>Активны сегодня</small><b>${escapeHtml(admin.metrics.active_today)}</b></article>
      <article class="metric-card"><small>Решений сегодня</small><b>${escapeHtml(admin.metrics.attempts_today)}</b></article>
      <article class="metric-card"><small>Средний первичный результат</small><b>${admin.metrics.average_primary_result ?? "—"}</b></article>
    </div></section>
    <section class="section two-column">
      <div class="panel"><div class="section-heading"><div><h2>Учебные сессии</h2></div></div><div class="table-scroll" role="region" tabindex="0" aria-label="Таблица учебных данных"><table class="admin-table"><thead><tr><th>Сессия</th><th>Попыток</th><th>Точность</th><th>Первичные</th><th>Активность</th><th>Статус</th></tr></thead><tbody>${usersRows}</tbody></table></div></div>
      <div class="panel"><div class="section-heading"><div><h2>Опубликованные задания</h2></div></div>
        <div class="forecast-number" style="font-size:40px">${escapeHtml(admin.content.coverage_percent)}<small>%</small></div>
        <div class="mini-track" style="height:8px"><i style="width:${escapeHtml(admin.content.coverage_percent)}%;background:var(--teal)"></i></div>
        <p class="data-note">${escapeHtml(admin.content.tasks_published)} из ${escapeHtml(admin.content.tasks_total)} заданий опубликованы · ${escapeHtml(admin.content.theory_chapters)} конспектов теории.</p>
      </div>
    </section>
    <section class="section panel"><div class="section-heading"><div><h2>Банк заданий</h2></div></div>
      <div class="table-scroll" role="region" tabindex="0" aria-label="Таблица учебных данных"><table class="admin-table"><thead><tr><th>№</th><th>Название</th><th>Код</th><th>Сложность</th><th>Баллы</th><th>Публикация</th></tr></thead><tbody>
        ${state.adminTasks.map((task) => `<tr><td>${escapeHtml(task.exam_number)}</td><td><b>${escapeHtml(task.title)}</b></td><td>${escapeHtml(task.codifier_code)}</td><td>${difficultyLabel(task.difficulty)}</td><td>${escapeHtml(task.max_primary_score)}</td><td><button class="toggle ${task.published ? "on" : ""}" data-toggle-task="${escapeHtml(task.id)}" role="switch" aria-checked="${escapeHtml(task.published)}" aria-label="Публикация задания ${escapeHtml(task.exam_number)}"><i></i></button></td></tr>`).join("")}
      </tbody></table></div>
    </section>`;
  document.querySelectorAll("[data-toggle-task]").forEach((button) => button.addEventListener("click", () => toggleTask(button.dataset.toggleTask, button)));
}

async function toggleTask(taskId, button) {
  if (button.disabled) return;
  button.disabled = true;
  const task = state.adminTasks.find((item) => item.id === taskId);
  try {
    const updated = await request(`/admin/tasks/${taskId}/status`, {
      method: "PATCH", body: JSON.stringify({ published: !task.published }),
    });
    Object.assign(task, updated);
    state.admin = await request("/admin/dashboard").catch((error) => {
      if (error.silent) throw error;
      toast("Публикация изменена, но сводку обновить не удалось.");
      return state.admin;
    });
    if (state.page === "admin") {
      renderAdmin();
      document.querySelector(`[data-toggle-task="${CSS.escape(taskId)}"]`)?.focus({ preventScroll: true });
    }
    toast(updated.published ? "Задание опубликовано" : "Задание снято с публикации");
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}

function bindGoButtons() {
  document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => goTo(button.dataset.go)));
}

function bindContentLinks() {
  document.querySelectorAll("[data-open-task], [data-open-theory], [data-roadmap-topic]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
    if (link.dataset.openTheory) {
      openTheory(link.dataset.openTheory);
      return;
    }
    const requestedTopic = link.dataset.roadmapTopic;
    const currentTopic = state.lesson.status === "active" ? state.lesson.topic.id : null;
    goTo(requestedTopic && requestedTopic !== currentTopic ? "roadmap" : "lessons");
    if (requestedTopic && requestedTopic !== currentTopic) toast("Эта тема откроется по порядку roadmap.");
  }));
}

function openPracticeTask(taskId) {
  const index = state.tasks.findIndex((task) => task.id === taskId);
  if (index < 0) return;
  state.practiceFilter = "all";
  state.currentTask = index;
  goTo("practice");
}

function openTheory(theoryId) {
  if (!state.completedTheory.some((item) => item.theory.id === theoryId)) {
    goTo("lessons");
    toast("Этот конспект появится в разделе после прохождения теории на уроке.");
    return;
  }
  state.focusTheory = theoryId;
  goTo("theory");
  requestAnimationFrame(() => {
    const chapter = document.querySelector(`#completed-theory-${CSS.escape(theoryId)}`);
    chapter?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
  });
}

function updateHomeworkBadge() {
  const badge = document.querySelector("#homework-badge");
  const count = state.homework?.status === "active" ? state.homework.pending_count : 0;
  badge.textContent = count;
  badge.classList.toggle("hidden", !count);
}

function setActiveNav() {
  let activeItem = null;
  document.querySelectorAll(".nav-item").forEach((item) => {
    const isActive = item.dataset.page === state.page;
    item.classList.toggle("active", isActive);
    if (isActive) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
    if (isActive) activeItem = item;
  });
  if (activeItem && activeItem.parentElement.scrollWidth > activeItem.parentElement.clientWidth) {
    activeItem.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
  }
}

function goTo(page) {
  if (page === "practice") page = "lessons";
  if (page === "admin" && state.role !== "admin") page = "dashboard";
  state.page = page;
  window.location.hash = page === "dashboard" ? "" : page;
  setActiveNav();
  render();
  view.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: scrollBehavior() });
}

function render() {
  if (!state.auth.user || !state.lesson) return;
  const pages = {
    dashboard: renderDashboard, roadmap: renderRoadmap, lessons: renderLessons,
    theory: renderTheory, homework: renderHomework, analytics: renderAnalytics, admin: renderAdmin,
  };
  (pages[state.page] || renderDashboard)();
}

function resetPrivateState() {
  Object.assign(state, {
    role: "student",
    page: "dashboard",
    analytics: null,
    roadmap: null,
    lesson: null,
    completedTheory: [],
    homework: null,
    dashboard: null,
    admin: null,
    adminUsers: [],
    adminTasks: [],
    currentTask: 0,
    practiceFilter: "all",
    focusTheory: null,
    lessonView: null,
    lessonTheoryPage: 0,
    lessonTheoryUnitId: null,
    aiTheoryAnswers: {},
    aiTheoryChecks: {},
    aiHints: {},
    dashboardSelectedDate: null,
    dashboardCalendarMonth: null,
  });
}

function setAuthStatus(message = "") {
  document.querySelector("#auth-status").textContent = message;
}

function authErrorMessage(message) {
  const translations = {
    "Invalid email or password": "Неверная почта или пароль.",
    "Email already exists": "Аккаунт с этой почтой уже существует.",
    "Display name already exists": "Это имя уже занято.",
    "Account already exists": "Такой аккаунт уже существует.",
    "Authentication required": "Войдите в аккаунт.",
    "User is unavailable": "Аккаунт недоступен. Войдите снова.",
  };
  if (translations[message]) return translations[message];
  if (message.includes("email address")) return "Проверьте адрес электронной почты.";
  if (message.includes("at least 8 characters")) return "Пароль должен содержать не менее 8 символов.";
  return message;
}

function setAuthBusy(busy) {
  state.auth.busy = busy;
  document.querySelectorAll(".auth-tab, .auth-submit").forEach((button) => { button.disabled = busy; });
  document.querySelector(".auth-card").setAttribute("aria-busy", String(busy));
}

function setAuthMode(mode, focus = false) {
  const isLogin = mode === "login";
  const loginTab = document.querySelector("#login-tab");
  const registerTab = document.querySelector("#register-tab");
  loginTab.classList.toggle("active", isLogin);
  registerTab.classList.toggle("active", !isLogin);
  loginTab.setAttribute("aria-selected", String(isLogin));
  registerTab.setAttribute("aria-selected", String(!isLogin));
  loginTab.tabIndex = isLogin ? 0 : -1;
  registerTab.tabIndex = isLogin ? -1 : 0;
  document.querySelector("#login-form").classList.toggle("hidden", !isLogin);
  document.querySelector("#register-form").classList.toggle("hidden", isLogin);
  setAuthStatus();
  if (focus) document.querySelector(isLogin ? "#login-email" : "#register-name").focus();
}

function showAuth(message = "") {
  document.querySelector("#auth-shell").classList.remove("hidden");
  document.querySelector("#app-shell").classList.add("hidden");
  setAuthStatus(message);
}

function showApplication() {
  document.querySelector("#auth-shell").classList.add("hidden");
  document.querySelector("#app-shell").classList.remove("hidden");
}

function accountInitials(name) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]).join("").toLocaleUpperCase("ru-RU") || "УЧ";
}

function updateAccountUI() {
  const user = state.auth.user;
  const isAdmin = state.role === "admin";
  const roleLabel = isAdmin ? "Администратор" : "Ученик";
  document.querySelectorAll(".admin-only").forEach((item) => item.classList.toggle("hidden", !isAdmin));
  document.querySelector("#role-name").textContent = user.display_name;
  document.querySelector("#role-label").textContent = roleLabel;
  document.querySelector(".avatar").textContent = accountInitials(user.display_name);
  document.querySelector("#account-menu-name").textContent = user.display_name;
  document.querySelector("#account-menu-role").textContent = roleLabel;
}

function toggleAccountMenu(force) {
  const menu = document.querySelector("#account-menu");
  const shouldOpen = force ?? menu.classList.contains("hidden");
  menu.classList.toggle("hidden", !shouldOpen);
  document.querySelector("#role-switch").setAttribute("aria-expanded", String(shouldOpen));
  if (shouldOpen) document.querySelector("#logout-button").focus();
}

function endLocalSession(message = "") {
  state.auth.generation += 1;
  state.auth.refreshPromise = null;
  clearTokens();
  state.auth.user = null;
  resetPrivateState();
  toggleAccountMenu(false);
  setAuthMode("login");
  view.replaceChildren();
  document.querySelector("#toast-region").replaceChildren();
  document.querySelector("#login-form").reset();
  document.querySelector("#register-form").reset();
  showAuth(message);
  document.querySelector("#login-email").focus();
}

async function initializeLearningView() {
  const generation = state.auth.generation;
  view.innerHTML = `<div class="loading-state"><span class="loader"></span><p>Собираем ваш учебный план…</p></div>`;
  try {
    await loadData();
    assertCurrentSession(generation);
    updateHomeworkBadge();
    const hash = window.location.hash.slice(1);
    const allowedPages = ["roadmap", "lessons", "theory", "homework", "analytics"];
    if (state.role === "admin") allowedPages.push("admin");
    if (allowedPages.includes(hash)) goTo(hash);
    else if (hash.startsWith("theory-")) openTheory(hash.slice("theory-".length));
    else if (hash.startsWith("practice-")) goTo("lessons");
    else {
      setActiveNav();
      render();
    }
  } catch (error) {
    if (error.silent) return;
    view.innerHTML = `<div class="error-card"><h2>Не удалось загрузить учебный план</h2><p>${escapeHtml(error.message)}</p><button class="secondary-button" id="retry-learning">Повторить</button></div>`;
    document.querySelector("#retry-learning").addEventListener("click", initializeLearningView);
  }
}

async function activateAuthenticatedSession(tokens = null) {
  if (tokens) { state.auth.generation += 1; persistTokens(tokens); }
  const user = await userRequest("/me");
  resetPrivateState();
  state.auth.user = user;
  state.role = user.role;
  updateAccountUI();
  showApplication();
  await initializeLearningView();
}

async function submitLogin(event) {
  event.preventDefault();
  if (state.auth.busy) return;
  setAuthBusy(true);
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  const data = new FormData(form);
  button.disabled = true;
  button.textContent = "Входим…";
  setAuthStatus();
  try {
    const tokens = await requestFrom(AUTH_API, "/login", {
      method: "POST",
      skipAuth: true,
      retryAuth: false,
      body: JSON.stringify({
        email: String(data.get("email")).trim(),
        password: String(data.get("password")),
      }),
    });
    await activateAuthenticatedSession(tokens);
    form.reset();
  } catch (error) {
    if (!error.silent) showAuth(authErrorMessage(error.message));
  } finally {
    button.disabled = false;
    button.textContent = "Войти";
    setAuthBusy(false);
  }
}

async function submitRegistration(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  const data = new FormData(form);
  const password = String(data.get("password"));
  if (password !== String(data.get("password_confirmation"))) {
    setAuthStatus("Пароли не совпадают.");
    return;
  }
  if (state.auth.busy) return;
  setAuthBusy(true);
  button.disabled = true;
  button.textContent = "Создаём аккаунт…";
  setAuthStatus();
  try {
    const tokens = await requestFrom(AUTH_API, "/register", {
      method: "POST",
      skipAuth: true,
      retryAuth: false,
      body: JSON.stringify({
        display_name: String(data.get("display_name")).trim(),
        email: String(data.get("email")).trim(),
        password,
      }),
    });
    await activateAuthenticatedSession(tokens);
    form.reset();
  } catch (error) {
    if (!error.silent) showAuth(authErrorMessage(error.message));
  } finally {
    button.disabled = false;
    button.textContent = "Создать аккаунт";
    setAuthBusy(false);
  }
}

async function logoutCurrentUser() {
  const refreshToken = state.auth.refreshToken;
  const accessToken = state.auth.accessToken;
  endLocalSession("Вы вышли из аккаунта.");
  if (!refreshToken || !accessToken) return;
  try {
    await requestFrom(AUTH_API, "/logout", {
      method: "POST", skipAuth: true, retryAuth: false,
      headers: { Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch (error) {
    if (!error.silent && !state.auth.user) setAuthStatus("Вы вышли на этом устройстве. Сервер не подтвердил отзыв сессии.");
  }
}

async function restoreSession() {
  if (!state.auth.accessToken || !state.auth.refreshToken) {
    showAuth();
    return;
  }
  try {
    await activateAuthenticatedSession();
  } catch {
    endLocalSession("Сессия завершилась. Войдите снова.");
  }
}

document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => goTo(item.dataset.page)));
document.querySelector("#login-tab").addEventListener("click", () => setAuthMode("login", true));
document.querySelector("#register-tab").addEventListener("click", () => setAuthMode("register", true));
document.querySelector("#login-form").addEventListener("submit", submitLogin);
document.querySelector("#register-form").addEventListener("submit", submitRegistration);
document.querySelector("#role-switch").addEventListener("click", () => toggleAccountMenu());
document.querySelector("#logout-button").addEventListener("click", logoutCurrentUser);
document.addEventListener("click", (event) => {
  const actions = document.querySelector(".topbar-actions");
  if (!actions.contains(event.target)) toggleAccountMenu(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !document.querySelector("#account-menu").classList.contains("hidden")) {
    toggleAccountMenu(false);
    document.querySelector("#role-switch")?.focus();
  }
});

document.querySelector(".auth-tabs").addEventListener("keydown", (event) => {
  if (state.auth.busy || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const login = event.key === "Home" || (event.key !== "End" && document.activeElement.id !== "login-tab");
  setAuthMode(login ? "login" : "register");
  document.querySelector(login ? "#login-tab" : "#register-tab").focus();
});
document.querySelector(".topbar-actions").addEventListener("focusout", (event) => {
  if (!event.currentTarget.contains(event.relatedTarget)) toggleAccountMenu(false);
});

window.addEventListener("hashchange", () => {
  if (!state.auth.user || !state.lesson) return;
  const hash = window.location.hash.slice(1);
  const pages = ["dashboard", "lessons", "theory", "homework", "roadmap", "analytics"];
  if (state.role === "admin") pages.push("admin");
  const page = pages.includes(hash) ? hash : "dashboard";
  if (page !== state.page) goTo(page);
});

const headerObserver = new ResizeObserver(([entry]) => {
  const height = entry.target.getBoundingClientRect().height;
  if (height > 0) document.documentElement.style.setProperty("--header-height", `${height}px`);
});
headerObserver.observe(document.querySelector(".site-header"));

restoreSession();
