const API = "/api/v1/exam/math-profile";
const AI_API = "/api/v1/ai";
const sessionId = new URLSearchParams(window.location.search).get("session_id") || "local-student";

const state = {
  role: "student",
  page: "dashboard",
  overview: null,
  tasks: [],
  theory: [],
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
  aiHints: {},
  dashboardSelectedDate: null,
  dashboardCalendarMonth: null,
};

const view = document.querySelector("#view");

async function requestFrom(baseUrl, path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Не удалось получить данные");
  return payload.data;
}

function request(path, options = {}) {
  return requestFrom(API, path, options);
}

function aiRequest(path, options = {}) {
  return requestFrom(AI_API, path, options);
}

async function loadData() {
  const [overview, tasks, theory, analytics, roadmap, lesson, homework, dashboard, admin, adminUsers, adminTasks, aiStatus] =
    await Promise.all([
      request("/overview"), request("/tasks"), request("/theory"),
      request(`/analytics?session_id=${sessionId}`),
      request(`/roadmap?session_id=${sessionId}`),
      request(`/lesson/current?session_id=${sessionId}`),
      request(`/homework/current?session_id=${sessionId}`),
      request(`/dashboard?session_id=${sessionId}`), request("/admin/dashboard"),
      request("/admin/users"), request("/admin/tasks"),
      aiRequest("/status").catch(() => ({ provider: "deepseek", model: "—", configured: false, capabilities: [] })),
    ]);
  Object.assign(state, { overview, tasks, theory, analytics, roadmap, lesson, homework, dashboard, admin, adminUsers, adminTasks, aiStatus });
  state.dashboardSelectedDate ||= dashboard.date;
  state.dashboardCalendarMonth ||= `${dashboard.date.slice(0, 7)}-01`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[char]));
}

function difficultyLabel(value) {
  return { basic: "Базовый", standard: "Средний", advanced: "Повышенный", expert: "Сложный" }[value] || value;
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

function percent(value) {
  return value === null || value === undefined ? "—" : `${value}%`;
}

function toast(message) {
  const region = document.querySelector("#toast-region");
  const item = document.createElement("div");
  item.className = "toast";
  item.textContent = message;
  region.append(item);
  setTimeout(() => item.remove(), 3200);
}

function pageHeader(eyebrow, title, description, action = "") {
  return `<header class="page-header">
    <div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1>${description ? `<p>${description}</p>` : ""}</div>
    ${action ? `<div class="header-action">${action}</div>` : ""}
  </header>`;
}

function topicCard(topic) {
  const metric = state.analytics.topics.find((item) => item.topic_id === topic.id);
  const symbols = { geometry: "△", vectors: "→", probability: "P", equations: "x", functions: "f", calculus: "∫", applied: "%", number_theory: "№" };
  const lessonTopic = state.roadmap.stages.flatMap((stage) => stage.topics).find((item) => item.id === topic.id);
  const lessonLabel = lessonTopic?.lesson_state === "completed" ? "Тема пройдена" : lessonTopic?.lesson_state === "current" ? "Продолжить занятие" : "Откроется по маршруту";
  return `<article class="topic-card" style="--topic-color:${topic.accent}">
    <div class="topic-top"><span class="topic-icon">${symbols[topic.id]}</span><span class="topic-score">${percent(metric.mastery)}</span></div>
    <h3>${topic.short_title}</h3><p>${topic.description}</p>
    <div class="mini-track"><i style="width:${metric.mastery ?? 0}%"></i></div>
    <div class="content-links"><a href="#lessons" data-roadmap-topic="${topic.id}">${lessonLabel}</a></div>
  </article>`;
}

function renderForecastCard(prediction) {
  const coverage = Math.round(prediction.covered_task_types / prediction.required_task_types * 100);
  if (prediction.available) {
    return `<aside class="forecast-card">
      <div class="card-kicker"><span>Полная диагностика</span><span class="model-badge">реальные ответы</span></div>
      <div class="forecast-number">${prediction.predicted_test_score}<small> / ${prediction.max_test_score} вторичных</small></div>
      <div class="forecast-range">Пройдены все ${prediction.required_task_types} типов заданий</div>
      <div class="forecast-track"><i style="width:100%"></i><b style="left:calc(100% - 8px)"></b></div>
      <p class="forecast-note">${prediction.basis}<br>${prediction.test_score_note}</p>
    </aside>`;
  }
  const missing = prediction.missing_task_numbers.slice(0, 8).join(", ");
  return `<aside class="forecast-card">
    <div class="card-kicker"><span>Результат диагностики</span><span class="model-badge">нет данных</span></div>
    <div class="forecast-number">—</div>
    <div class="forecast-range">Пройдено ${prediction.covered_task_types} из ${prediction.required_task_types} типов</div>
    <div class="forecast-track"><i style="width:${coverage}%"></i><b style="left:calc(${coverage}% - 8px)"></b></div>
    <p class="forecast-note">${prediction.basis}${missing ? `<br>Остались номера: ${missing}${prediction.missing_task_numbers.length > 8 ? "…" : ""}` : ""}</p>
  </aside>`;
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

function renderRoadmapSubtopics(subtopics, compact = false) {
  return `<div class="roadmap-subtopics ${compact ? "compact" : ""}">${subtopics.map((subtopic) => `
    <div class="roadmap-subtopic ${subtopic.state}">
      <div><span>${String(subtopic.order).padStart(2, "0")}</span><b>${escapeHtml(subtopic.title)}</b><strong>${subtopic.progress}%</strong></div>
      <i role="progressbar" aria-label="${escapeHtml(subtopic.title)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${subtopic.progress}"><b style="width:${subtopic.progress}%"></b></i>
    </div>`).join("")}</div>`;
}

function renderCourseOrderMain(item) {
  const heading = `<div><h3>${escapeHtml(item.topic.short_title)}</h3></div>`;
  const content = `<div class="course-task-numbers">${item.task_numbers.map((number) => `<span>№${number}</span>`).join("")}</div>${renderRoadmapSubtopics(item.subtopics)}`;

  if (["vectors", "geometry", "probability"].includes(item.topic.id)) {
    return `<div class="course-order-main"><details class="course-topic-disclosure" open>
      <summary>${heading}<i aria-hidden="true">⌄</i></summary>
      <div class="course-topic-disclosure-content">${content}</div>
    </details></div>`;
  }
  return `<div class="course-order-main">${heading}${content}</div>`;
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
    <div class="day-plan-card-top"><span class="agenda-kind">Текущий урок</span><span>${lesson.estimated_minutes} мин</span></div>
    <h3>${escapeHtml(lesson.title)}</h3>
    <div class="lesson-progress"><div><span>Прогресс урока</span><b>${lesson.progress}%</b></div><i role="progressbar" aria-label="Прогресс урока ${escapeHtml(lesson.title)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${lesson.progress}"><b style="width:${lesson.progress}%"></b></i></div>
    <div class="day-plan-card-footer"><span>${escapeHtml(lesson.step_label)} · до 100%</span><button class="primary-button" data-go="lessons">Продолжить урок →</button></div>
  </article>`;
}

function renderTodayPlan(data) {
  const homework = data.today.homework;
  const homeworkCard = homework
    ? `<article class="day-plan-card homework"><div class="day-plan-card-top"><span class="agenda-kind">Домашнее задание</span><span>до ${formatDate(homework.due_date)}</span></div><h3>${escapeHtml(homework.title)}</h3><div class="lesson-progress"><div><span>Выполнено</span><b>${homework.progress}%</b></div><i role="progressbar" aria-label="Прогресс домашнего задания" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${homework.progress}"><b style="width:${homework.progress}%"></b></i></div><div class="day-plan-card-footer"><span>${homework.estimated_minutes} мин самостоятельно</span><button class="secondary-button" data-go="homework">Открыть ДЗ →</button></div></article>`
    : `<article class="day-plan-card homework empty"><span class="agenda-kind">Домашнее задание</span><h3>Пока не назначено</h3><button class="secondary-button" data-go="homework">Раздел ДЗ</button></article>`;
  const reviews = data.today.reviews.map((item) => `<article class="agenda-row review"><span>Повторение</span><div><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.action)}</small></div><button class="schedule-arrow" data-go="lessons" aria-label="Открыть повторение">→</button></article>`).join("");
  return `<div class="day-plan-cards">${renderLessonPlanCard(data.today.lesson)}${homeworkCard}${reviews}</div>`;
}

function renderScheduledPlan(data, selectedDate) {
  const labels = { lesson: "Урок", homework: "Домашнее задание", review: "Повторение" };
  const items = data.schedule.filter((item) => item.date === selectedDate);
  if (!items.length) return '<div class="selected-day-empty"><span>Свободный день</span><p>На эту дату в текущем роадмапе ничего не запланировано.</p></div>';
  return `<div class="agenda-list">${items.map((item) => `<article class="agenda-row ${item.kind}"><span>${labels[item.kind]}</span><div><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.detail)}</small>${Number.isInteger(item.progress) ? `<i><b style="width:${item.progress}%"></b></i>` : ""}</div><button class="schedule-arrow" data-go="${item.kind === "homework" ? "homework" : "lessons"}" aria-label="Открыть ${labels[item.kind].toLowerCase()}">→</button></article>`).join("")}</div>`;
}

function renderDashboard() {
  const data = state.dashboard;
  const metrics = data.metrics;
  const selectedDate = state.dashboardSelectedDate || data.date;
  const isToday = selectedDate === data.date;
  const score = metrics.prediction_available ? metrics.expected_test_score : "—";
  view.innerHTML = `${pageHeader("Главная", "Учебный маршрут", "")}
    <section class="section dashboard-calendar-section">
      <div class="section-heading"><div><h2>Расписание</h2></div>${isToday ? "" : '<button class="secondary-button compact-button" data-calendar-today>Сегодня</button>'}</div>
      <div class="calendar-layout">${renderDashboardCalendar(data)}
        <div class="selected-day-plan"><div class="selected-day-heading"><div><span>${isToday ? "План на сегодня" : "Выбранный день"}</span><h3>${formatLongDate(selectedDate)}</h3></div></div>
          ${isToday ? renderTodayPlan(data) : renderScheduledPlan(data, selectedDate)}
        </div>
      </div>
    </section>

    <section class="dashboard-overview" aria-label="Общие сведения об обучении">
      <article><span>Ожидаемый балл ЕГЭ</span><b>${score}<small> / ${metrics.max_test_score}</small></b></article>
      <article><span>Серия занятий</span><b>${metrics.streak_days}<small> дн.</small></b></article>
    </section>`;

  document.querySelectorAll("[data-calendar-date]").forEach((button) => button.addEventListener("click", () => {
    state.dashboardSelectedDate = button.dataset.calendarDate;
    renderDashboard();
  }));
  document.querySelectorAll("[data-calendar-shift]").forEach((button) => button.addEventListener("click", () => {
    state.dashboardCalendarMonth = shiftCalendarMonth(state.dashboardCalendarMonth, Number(button.dataset.calendarShift));
    state.dashboardSelectedDate = state.dashboardCalendarMonth.slice(0, 7) === data.date.slice(0, 7) ? data.date : state.dashboardCalendarMonth;
    renderDashboard();
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
  const stepLabels = { theory: "Теория", practice: "Практика", complete: "Урок пройден" };
  view.innerHTML = `${pageHeader("Персональный роадмап", "Путеводитель по курсу", "")}
    <section class="course-order-section">
      <div class="section-heading"><div><h2>Порядок тем</h2></div></div>
      <ol class="course-order">${roadmap.lesson_order.map((item) => `<li class="course-order-item ${item.lesson_state}">
        <span class="course-position">${item.lesson_state === "completed" ? "✓" : item.position}</span>
        ${renderCourseOrderMain(item)}
        <div class="course-order-state"><strong>${item.progress}%</strong><i><b style="width:${item.progress}%"></b></i><b>${item.lesson_state === "completed" ? "Пройдено" : item.lesson_state === "current" ? `Сейчас: ${stepLabels[item.current_step]}` : "Впереди"}</b><small>${item.homework_status === "assigned" ? "ДЗ назначено отдельно" : item.homework_status === "completed" ? "ДЗ выполнено" : "ДЗ после практики"}</small>${item.lesson_state === "current" ? '<button class="text-button" data-go="lessons">Открыть урок →</button>' : ""}</div>
      </li>`).join("")}</ol>
    </section>`;
  bindGoButtons();
}

function lessonStepTitle(step) {
  return { theory: "Теория", practice: "Практика" }[step] || "Завершено";
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

function aiProviderLabel() {
  return { deepseek: "DeepSeek", openrouter: "OpenRouter" }[state.aiStatus?.provider]
    || state.aiStatus?.provider
    || "ИИ";
}

function renderAIModelBadge() {
  return `<span class="ai-model-badge ${aiReady() ? "ready" : "waiting"}"><i></i>${aiReady() ? `${aiProviderLabel()} подключён` : "ожидает API-ключ"}</span>`;
}

function renderAITheoryAnswer(answer) {
  if (!answer) return "";
  return `<article class="ai-answer">
    <span>Персональное объяснение</span><h4>${escapeHtml(answer.title)}</h4>
    <p>${escapeHtml(answer.explanation)}</p>
    <div class="ai-example"><b>Новый пример</b><p>${escapeHtml(answer.example)}</p></div>
    <div class="ai-self-check"><b>Проверь себя</b><p>${escapeHtml(answer.check_question)}</p></div>
    <small>${escapeHtml(aiProviderLabel())} · только текущий раздел теории</small>
  </article>`;
}

function renderAITheoryPanel(lesson) {
  const section = lesson.theory.sections?.[state.lessonTheoryPage];
  if (!section) return "";
  const answerKey = `${lesson.unit_id}:${section.id}`;
  const answer = state.aiTheoryAnswers[answerKey];
  const disabled = aiReady() ? "" : "disabled";
  return `<section class="ai-tutor-card theory-ai-card">
    <header><div><span class="ai-kicker">ИИ-репетитор</span><h3>Спросить по этой странице</h3><p>Ответ ограничен разделом «${escapeHtml(section.title)}» и экзаменационной теорией урока.</p></div>${renderAIModelBadge()}</header>
    <form class="ai-question-form" id="ai-theory-form">
      <label for="ai-theory-question">Что осталось непонятно?</label>
      <div><input id="ai-theory-question" name="question" maxlength="500" placeholder="Например: объясни проще и приведи другой пример" ${disabled}><button class="secondary-button" type="submit" ${disabled}>Объяснить</button></div>
    </form>
    ${aiReady() ? "" : '<p class="ai-setup-note">Интерфейс готов. После добавления <code>DEEPSEEK_API_KEY</code> в локальный .env кнопка станет активной.</p>'}
    <div class="ai-response-slot" id="ai-theory-response" aria-live="polite">${renderAITheoryAnswer(answer)}</div>
  </section>`;
}

async function requestAITheoryExplanation(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  const section = state.lesson.theory.sections[state.lessonTheoryPage];
  const answerKey = `${state.lesson.unit_id}:${section.id}`;
  const question = new FormData(form).get("question")?.trim() || "Объясни этот раздел проще и проверь, понял ли я его.";
  button.disabled = true;
  button.textContent = "Объясняю…";
  try {
    const answer = await aiRequest("/explain-theory", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        lesson_unit_id: state.lesson.unit_id,
        theory_section_id: section.id,
        question,
      }),
    });
    state.aiTheoryAnswers[answerKey] = answer;
    document.querySelector("#ai-theory-response").innerHTML = renderAITheoryAnswer(answer);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Объяснить";
  }
}

function bindAITheoryControls() {
  document.querySelector("#ai-theory-form")?.addEventListener("submit", requestAITheoryExplanation);
}

function renderAIHintItems(hints) {
  if (!hints.length) return '<p class="ai-empty-response">Начните с мягкой подсказки: ИИ направит мысль, но не выдаст ответ.</p>';
  return hints.map((hint) => `<article class="ai-hint-item"><span>Подсказка ${hint.level}</span><b>${escapeHtml(hint.focus)}</b><p>${escapeHtml(hint.hint)}</p><small>${escapeHtml(hint.self_check)}</small></article>`).join("");
}

function renderAIHintPanel(lesson) {
  const taskKey = lesson.practice_task.lesson_task_key;
  const hints = state.aiHints[taskKey] || [];
  const nextLevel = hints.length + 1;
  const disabled = !aiReady() || nextLevel > 3;
  const buttonLabel = !aiReady() ? "Нужен API-ключ" : nextLevel > 3 ? "Все подсказки получены" : `Подсказка ${nextLevel} из 3`;
  return `<section class="ai-tutor-card hint-ai-card">
    <header><div><span class="ai-kicker">Помощь без готового ответа</span><h3>Застряли на шаге?</h3><p>Сначала вопрос-направление, затем правило и только потом первый вычислительный шаг.</p></div>${renderAIModelBadge()}</header>
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
        session_id: sessionId,
        lesson_unit_id: state.lesson.unit_id,
        lesson_task_key: task.lesson_task_key,
        level,
      }),
    });
    state.aiHints[task.lesson_task_key] = [...hints, hint];
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
    <span>AI-разбор фактической попытки</span><h4>${escapeHtml(answer.diagnosis)}</h4>
    <dl><div><dt>На чём основан вывод</dt><dd>${escapeHtml(answer.evidence)}</dd></div><div><dt>Почему возникла ошибка</dt><dd>${escapeHtml(answer.explanation)}</dd></div><div><dt>Короткий микроурок</dt><dd>${escapeHtml(answer.micro_lesson)}</dd></div><div><dt>Следующее действие</dt><dd>${escapeHtml(answer.next_action)}</dd></div></dl>
    <small>${escapeHtml(answer.confidence_note)}</small>
  </article>`;
}

function renderAIErrorAction(attemptId) {
  const disabled = aiReady() ? "" : "disabled";
  return `<section class="ai-error-control">
    <div><b>Понять причину ошибки</b><span>${aiReady() ? "ИИ сопоставит ответ с решением и текущей теорией." : "AI-разбор станет доступен после подключения ключа."}</span></div>
    <button class="secondary-button" type="button" data-ai-error="${escapeHtml(attemptId)}" ${disabled}>Разобрать с ИИ</button>
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
      body: JSON.stringify({ session_id: sessionId, attempt_id: attemptId }),
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
  const progress = Math.round(((pageIndex + 1) / chapter.sections.length) * 100);
  const introduction = pageIndex === 0 ? `<section class="exam-scope">
      <div><span>${escapeHtml(scope.label)}</span><h3>Что действительно проверяют</h3><p>${escapeHtml(scope.text)}</p></div>
      <ul>${scope.skills.map((skill) => `<li>${escapeHtml(skill)}</li>`).join("")}</ul>
    </section>` : "";
  const review = pageIndex === lastPage ? `<section class="exam-pattern-section"><p class="eyebrow">Пять формулировок — один набор правил</p><h3>Как узнать тип задания</h3>
      <div class="exam-pattern-grid">${chapter.exam_patterns.map((pattern, index) => `<article><span>0${index + 1}</span><b>${escapeHtml(pattern.title)}</b><p>${escapeHtml(pattern.method)}</p></article>`).join("")}</div>
    </section>
    <div class="theory-review-grid">
      <section class="mistake-card"><p class="eyebrow">Типичные ошибки</p><h3>Где теряют балл</h3><ul>${chapter.mistakes.map((mistake) => `<li>${escapeHtml(mistake)}</li>`).join("")}</ul></section>
      <section class="checklist-card"><p class="eyebrow">Перед ответом</p><h3>Проверка за 20 секунд</h3><ol>${chapter.checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol></section>
    </div>
    <footer class="theory-reference"><b>Основа конспекта</b><span>${escapeHtml(chapter.reference.title)} · ${escapeHtml(chapter.reference.sections)}</span><small>${escapeHtml(chapter.reference.note)}</small></footer>` : "";

  return `<div class="theory-page-status">
      <div><span>Теория</span><b>Страница ${pageIndex + 1} из ${chapter.sections.length}</b></div>
      <strong>${progress}%</strong>
      <i aria-label="Прогресс теории: ${progress}%"><b style="width:${progress}%"></b></i>
    </div>
    ${introduction}
    <div class="detailed-theory"><section class="theory-section" id="theory-section-${escapeHtml(section.id)}">
      <header><span>${escapeHtml(section.number)}</span><div><p>Экзаменационная база</p><h3>${escapeHtml(section.title)}</h3></div></header>
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

function renderTheoryActions(chapter, reviewingTheory, lesson) {
  if (!chapter.sections?.length) {
    return `<div class="lesson-action"><span>${reviewingTheory ? `Выполнено ${lesson.practice.attempted_tasks} из ${lesson.practice.total_tasks} задач` : `${chapter.read_minutes} минут на изучение`}</span><button class="primary-button" ${reviewingTheory ? "data-return-practice" : 'id="complete-theory"'}>${reviewingTheory ? "Вернуться к практике →" : "Перейти к практике →"}</button></div>`;
  }

  const pageIndex = state.lessonTheoryPage;
  const lastPage = chapter.sections.length - 1;
  return `<div class="theory-page-actions">
      <button class="secondary-button" type="button" data-theory-prev ${pageIndex === 0 ? "disabled" : ""}>← Назад</button>
      ${pageIndex < lastPage
        ? `<button class="primary-button" type="button" data-theory-next>Следующая страница →</button>`
        : `<button class="primary-button" type="button" ${reviewingTheory ? "data-return-practice" : 'id="complete-theory"'}>${reviewingTheory ? "Вернуться к практике →" : "Перейти к практике →"}</button>`}
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
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindTheoryPageControls() {
  document.querySelector("[data-theory-prev]")?.addEventListener("click", () => openTheoryPage(state.lessonTheoryPage - 1));
  document.querySelector("[data-theory-next]")?.addEventListener("click", () => openTheoryPage(state.lessonTheoryPage + 1));
}

function renderLessons() {
  const lesson = state.lesson;
  if (lesson.status === "completed") {
    view.innerHTML = `${pageHeader("Уроки", "Учебный маршрут завершён", "Все темы пройдены.")}
      <section class="lesson-complete"><span>✓</span><h2>Отличная работа</h2><p>Вы завершили ${lesson.total_units} уроков. Назначенные самостоятельные работы остаются в отдельном разделе.</p><div class="complete-actions"><button class="secondary-button" data-go="roadmap">Посмотреть роадмап</button><button class="primary-button" data-go="homework">Домашние задания →</button></div></section>`;
    bindGoButtons();
    return;
  }

  syncTheoryPages(lesson);

  const currentStep = lesson.current_step;
  const reviewingTheory = currentStep === "practice" && state.lessonView === "theory";
  const isTheory = currentStep === "theory" || reviewingTheory;
  const task = lesson.practice_task;
  const stepContent = isTheory ? `<article class="lesson-panel lesson-theory">
      ${reviewingTheory ? '<div class="review-theory-banner"><b>Повторение теории</b><span>Прогресс практики сохранён. Можно открыть любую подтему.</span><button class="secondary-button" type="button" data-return-practice>Вернуться к задаче →</button></div>' : ""}
      <p class="eyebrow">${lesson.theory.eyebrow}</p>
      <h2>${lesson.theory.title}</h2>
      <p class="lesson-summary">${lesson.theory.summary}</p>
      ${renderLessonTheory(lesson.theory)}
      ${renderAITheoryPanel(lesson)}
      ${!lesson.theory.sections?.length || state.lessonTheoryPage === lesson.theory.sections.length - 1 ? `<aside class="theory-tip"><b>Совет перед практикой</b>${lesson.theory.tip}</aside>` : ""}
      ${renderTheoryActions(lesson.theory, reviewingTheory, lesson)}
    </article>` : `<article class="lesson-panel lesson-task">
      <div class="practice-banner"><b>Практика: ${escapeHtml(lesson.topic.short_title)}</b><span>Все ${lesson.practice.total_tasks} заданий проверяют только теорию этого урока.</span></div>
      <div class="practice-toolbar"><div><span>Задача ${lesson.practice.current_task_number} из ${lesson.practice.total_tasks}</span><i><b style="width:${lesson.practice.attempted_tasks / lesson.practice.total_tasks * 100}%"></b></i></div><button class="secondary-button" id="review-theory">← Вернуться к теории</button></div>
      <div class="task-meta"><span class="tag accent">Задание ${task.exam_number}</span><span class="tag">${difficultyLabel(task.difficulty)}</span><span class="tag">Код ${task.codifier_code}</span><span class="tag topic-tag">Тема: ${escapeHtml(lesson.topic.short_title)}</span></div>
      <h2>${task.title}</h2><p class="task-prompt">${task.prompt}</p>
      ${renderAIHintPanel(lesson)}
      <form class="answer-block" id="lesson-answer-form"><label for="lesson-answer">Ваш ответ</label><div class="answer-row">
        <input id="lesson-answer" name="answer" autocomplete="off" placeholder="Введите ответ" required>
        <button class="primary-button" type="submit">Проверить</button></div></form>
      <div id="feedback-slot"></div>
      <p class="task-source">Источник типа: <a href="${escapeHtml(task.source.url)}" target="_blank" rel="noreferrer">${escapeHtml(task.source.label)}</a> · условие адаптировано и не копирует оригинал дословно</p>
    </article>`;

  view.innerHTML = `${pageHeader("Текущий урок", lesson.topic.short_title, `${lesson.stage.number}-й этап · ${lesson.stage.title}`,
    '<button class="secondary-button" data-go="roadmap">Посмотреть роадмап</button>')}
    <section class="lesson-shell">
      <div class="lesson-context"><span>Тема ${lesson.position} из ${lesson.total_units}</span><b>${lesson.topic.title}</b><small>${lesson.topic.description}</small></div>
      <div class="lesson-progress"><i style="width:${lesson.overall_progress}%"></i></div>
      <ol class="lesson-stepper two-steps">${lesson.steps.map((step, index) => `<li class="lesson-step ${step.state}"><span>${step.state === "completed" ? "✓" : index + 1}</span><div><b>${step.label}</b><small>${step.state === "current" ? "Текущий шаг" : step.state === "completed" ? "Готово" : "Сначала предыдущий шаг"}</small></div></li>`).join("")}</ol>
      <div class="lesson-current-label"><span>${reviewingTheory ? "Можно вернуться" : "Сейчас"}</span><b>${reviewingTheory ? "Повторение теории" : lessonStepTitle(currentStep)}</b></div>
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
  } else {
    document.querySelector("#review-theory").addEventListener("click", reviewCurrentTheory);
    bindAIHintControls();
    document.querySelector("#lesson-answer-form").addEventListener("submit", submitLessonAnswer);
  }
}

function renderHomework() {
  const homework = state.homework;
  if (homework.status !== "active") {
    view.innerHTML = `${pageHeader("Домашние задания", "Самостоятельная работа", "Отдельно от урока и практики.", '<button class="secondary-button" data-go="lessons">Перейти к урокам</button>')}
      <section class="homework-empty"><span>✓</span><h2>Все задания выполнены</h2><p>${escapeHtml(homework.message)}</p><button class="primary-button" data-go="dashboard">Вернуться на главную</button></section>`;
    bindGoButtons();
    return;
  }
  const task = homework.task;
  view.innerHTML = `${pageHeader("Домашние задания", homework.topic.short_title, `Сдать до ${formatDate(homework.due_date)} · задача ${homework.current_task_number} из ${homework.total_tasks}`, '<button class="secondary-button" data-go="lessons">К урокам</button>')}
    <section class="homework-shell">
      <aside class="homework-separation-note"><span>ДЗ</span><div><b>Самостоятельная работа</b><p>Теория и практика остаются в разделе «Уроки».</p></div></aside>
      <article class="lesson-panel lesson-task homework-workspace">
        <div class="homework-banner"><b>Домашнее задание · ${homework.total_tasks} задач</b><span>Самостоятельно · после урока «${escapeHtml(homework.topic.short_title)}»</span></div>
        <div class="practice-toolbar homework-progress"><div><span>Задача ${homework.current_task_number} из ${homework.total_tasks}</span><i><b style="width:${homework.attempted_tasks / homework.total_tasks * 100}%"></b></i></div><small>Осталось: ${homework.remaining_tasks}</small></div>
        <div class="task-meta"><span class="tag accent">Задание ${task.exam_number}</span><span class="tag">${difficultyLabel(task.difficulty)}</span><span class="tag">Код ${task.codifier_code}</span></div>
        <h2>${escapeHtml(task.title)}</h2><p class="task-prompt">${escapeHtml(task.prompt)}</p>
        <form class="answer-block" id="homework-answer-form"><label for="homework-answer">Ваш ответ</label><div class="answer-row">
          <input id="homework-answer" name="answer" autocomplete="off" placeholder="Введите ответ" required>
          <button class="primary-button" type="submit">Сдать работу</button></div></form>
        <div id="feedback-slot"></div>
        <p class="task-source">Источник типа: <a href="${escapeHtml(task.source.url)}" target="_blank" rel="noreferrer">${escapeHtml(task.source.label)}</a> · условие адаптировано и не копирует оригинал дословно</p>
      </article>
    </section>`;
  bindGoButtons();
  document.querySelector("#homework-answer-form").addEventListener("submit", submitHomeworkAnswer);
}

async function refreshLearningData() {
  const [analytics, roadmap, lesson, homework, dashboard, admin, adminUsers] = await Promise.all([
    request(`/analytics?session_id=${sessionId}`), request(`/roadmap?session_id=${sessionId}`),
    request(`/lesson/current?session_id=${sessionId}`),
    request(`/homework/current?session_id=${sessionId}`),
    request(`/dashboard?session_id=${sessionId}`),
    request("/admin/dashboard"), request("/admin/users"),
  ]);
  Object.assign(state, { analytics, roadmap, lesson, homework, dashboard, admin, adminUsers });
  updateHomeworkBadge();
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
      body: JSON.stringify({ session_id: sessionId, lesson_unit_id: state.lesson.unit_id }),
    });
    await refreshLearningData();
    state.lessonView = null;
    state.lessonTheoryPage = 0;
    renderLessons();
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
        session_id: sessionId,
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
    await refreshLearningData();
    state.lessonView = null;
    const correctTitle = result.lesson_unit_complete
      ? `Практика «${escapeHtml(practiceTopic)}» завершена`
      : `Верно — задача ${practiceNumber} из ${practiceTotal}`;
    const incorrectTitle = `Неверно — задача ${practiceNumber} из ${practiceTotal} завершена`;
    document.querySelector("#feedback-slot").innerHTML = `<div class="feedback ${result.is_correct ? "correct" : "incorrect"}">
      <b>${result.is_correct ? correctTitle : incorrectTitle}</b>
      ${result.is_correct ? "" : `Верный ответ: ${escapeHtml(result.correct_answer)}.<br>`}${result.explanation}<br><span style="opacity:.78">${result.recommendation}</span>
      ${result.is_correct ? "" : renderAIErrorAction(result.attempt.id)}
      <div class="feedback-action"><button class="primary-button" id="lesson-next">${result.lesson_unit_complete ? "Следующий урок" : `Следующая задача по теме «${escapeHtml(practiceTopic)}»`} →</button>${result.lesson_unit_complete ? '<button class="secondary-button" id="lesson-homework">Открыть ДЗ отдельно</button>' : ""}</div>
    </div>`;
    form.classList.add("hidden");
    if (!result.is_correct) bindAIErrorAnalysis();
    document.querySelector("#lesson-next").addEventListener("click", renderLessons);
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
        session_id: sessionId,
        task_id: assignment.task.id,
        answer,
        duration_seconds: 120,
        mode: "homework",
        lesson_unit_id: assignment.unit_id,
        lesson_task_key: assignment.task.lesson_task_key,
      }),
    });
    await refreshLearningData();
    const title = result.is_correct
      ? result.homework_unit_complete ? "Домашняя работа завершена" : `Верно — задача ${homeworkNumber} из ${homeworkTotal}`
      : `Неверно — задача ${homeworkNumber} из ${homeworkTotal} завершена`;
    document.querySelector("#feedback-slot").innerHTML = `<div class="feedback ${result.is_correct ? "correct" : "incorrect"}">
      <b>${title}</b>
      ${result.is_correct ? "" : `Верный ответ: ${escapeHtml(result.correct_answer)}.<br>`}${escapeHtml(result.explanation)}<br><span style="opacity:.78">${escapeHtml(result.recommendation)}</span>
      ${result.is_correct ? "" : renderAIErrorAction(result.attempt.id)}
      <div class="feedback-action"><button class="primary-button" id="homework-next">${result.homework_unit_complete ? "Готово" : "Следующая задача"} →</button></div>
    </div>`;
    form.classList.add("hidden");
    if (!result.is_correct) bindAIErrorAnalysis();
    document.querySelector("#homework-next").addEventListener("click", () => {
      if (state.homework.status === "active") renderHomework();
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
  view.innerHTML = `${pageHeader("Тренажёр", "Практика по структуре ЕГЭ", "19 позиций, официальная разбалловка и мгновенная обратная связь. Задания — учебные аналоги по типам ФИПИ.")}
    <div class="practice-layout">
      <aside class="task-sidebar">
        <div class="filter-group"><label>Сложность</label>
          ${[["all", "Все"], ["basic", "База"], ["standard", "Средние"], ["advanced", "Повышенные"], ["expert", "Сложные"]].map(([value, label]) => `<button class="filter-chip ${state.practiceFilter === value ? "active" : ""}" data-filter="${value}">${label}</button>`).join("")}
        </div>
        <div class="filter-group"><label>Номер задания</label><div class="task-numbers">
          ${list.map((item, index) => `<button class="task-number ${index === state.currentTask ? "active" : ""} ${item.difficulty === "expert" ? "complex" : ""}" data-task-index="${index}">${item.exam_number}</button>`).join("")}
        </div></div>
        <p class="data-note">Часть 1: №1–12 по 1 баллу.<br>Часть 2: №13–19 до 4 баллов.<br>№14 и №17 относятся к сложным.</p>
      </aside>
      <section class="task-workspace">
        <div class="task-meta"><span class="tag accent">Задание ${task.exam_number}</span><span class="tag">${difficultyLabel(task.difficulty)}</span><span class="tag">Код ${task.codifier_code}</span><span class="tag">до ${task.max_primary_score} перв. балл.</span></div>
        <h2>${task.title}</h2><p class="task-prompt">${task.prompt}</p>
        <div class="content-links prominent"><a href="#theory-${task.theory_id}" data-open-theory="${task.theory_id}">Открыть теорию по теме →</a></div>
        <form class="answer-block" id="answer-form"><label for="answer">Ваш ответ</label><div class="answer-row">
          <input id="answer" name="answer" autocomplete="off" placeholder="Введите число" required>
          <button class="primary-button" type="submit">Проверить</button></div></form>
        <div id="feedback-slot"></div>
        <p class="task-source">Источник типа: <a href="${task.source.url}" target="_blank" rel="noreferrer">открытые материалы ФИПИ ЕГЭ-2026</a> · формулировка адаптирована для прототипа</p>
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
  const list = filteredTasks();
  const task = list[state.currentTask];
  const answer = new FormData(event.currentTarget).get("answer");
  const button = event.currentTarget.querySelector("button");
  button.disabled = true; button.textContent = "Проверяем…";
  try {
    const result = await request("/attempts", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, task_id: task.id, answer, duration_seconds: 90 }),
    });
    document.querySelector("#feedback-slot").innerHTML = `<div class="feedback ${result.is_correct ? "correct" : "incorrect"}">
      <b>${result.is_correct ? "Верно — балл ваш" : `Пока не так. Ответ: ${result.correct_answer}`}</b>
      ${result.explanation}<br><span style="opacity:.78">${result.recommendation}</span></div>`;
    const [analytics, roadmap, admin, adminUsers] = await Promise.all([
      request(`/analytics?session_id=${sessionId}`), request(`/roadmap?session_id=${sessionId}`),
      request("/admin/dashboard"), request("/admin/users"),
    ]);
    Object.assign(state, { analytics, roadmap, admin, adminUsers });
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false; button.textContent = "Проверить";
  }
}

function renderTheory() {
  view.innerHTML = `${pageHeader("Библиотека", "Теория по темам ЕГЭ", "Каждый конспект связан с конкретными номерами практики.")}
    <div class="theory-grid">${state.theory.map((chapter) => {
    const tasks = state.tasks.filter((task) => task.theory_id === chapter.id);
    return `<article class="theory-card ${state.focusTheory === chapter.id ? "focused" : ""}" id="theory-${chapter.id}">
        <p class="eyebrow">${chapter.eyebrow}</p><h2>${chapter.title}</h2><p>${chapter.summary}</p>
        <ul class="formula-list">${chapter.key_points.map((point) => `<li>${point}</li>`).join("")}</ul>
        <div class="task-link-row">${tasks.map((task) => `<a href="#practice-${task.id}" data-open-task="${task.id}" class="task-link ${task.difficulty === "expert" ? "complex" : ""}">Практика №${task.exam_number}</a>`).join("")}</div>
        <div class="theory-foot"><span>${chapter.read_minutes} минут</span><button class="text-button" data-theory="${chapter.id}">Совет по теме</button></div>
      </article>`;
  }).join("")}</div>`;
  document.querySelectorAll("[data-theory]").forEach((button) => button.addEventListener("click", () => {
    const chapter = state.theory.find((item) => item.id === button.dataset.theory);
    toast(`Совет: ${chapter.tip}`);
  }));
  bindContentLinks();
}

function renderPredictionHistory(history, maxScore) {
  if (!history.length) return `<div class="prediction-history-empty"><b>График появится после полной диагностики</b><p>Сначала нужен хотя бы один реальный ответ по каждому из 19 типов заданий. До этого тестовый балл не подставляется.</p><span>Покрытие: ${state.analytics.prediction.covered_task_types} из ${state.analytics.prediction.required_task_types}</span></div>`;
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
    </svg><div class="chart-labels score-chart-labels">${history.map((item) => `<span>${item.label}<br><b>${item.score} / ${item.max_score}</b></span>`).join("")}</div>`;
}

function renderAnalytics() {
  const data = state.analytics;
  const prediction = data.prediction;
  view.innerHTML = `${pageHeader("Результаты", "Аналитика", "Прогресс, ошибки и прогноз по реальным ответам.")}
    <div class="analytics-grid">
      <article class="metric-card"><span class="metric-icon">∑</span><small>Попыток</small><b>${data.summary.attempts}</b></article>
      <article class="metric-card"><span class="metric-icon teal">✓</span><small>Верных</small><b>${data.summary.correct}<span class="metric-suffix"> / ${data.summary.attempts}</span></b></article>
      <article class="metric-card"><span class="metric-icon yellow">№</span><small>Типов пройдено</small><b>${prediction.covered_task_types}<span class="metric-suffix"> / ${prediction.required_task_types}</span></b></article>
      <article class="metric-card"><span class="metric-icon dark">↗</span><small>Прогноз ЕГЭ</small><b>${prediction.available ? prediction.predicted_test_score : "—"}<span class="metric-suffix"> / ${prediction.max_test_score}</span></b></article>

      <section class="panel chart-panel"><div class="section-heading"><div><h2>Динамика балла</h2><p>По последним реальным ответам</p></div><span class="model-badge">ЕГЭ-2026</span></div>
        ${renderPredictionHistory(data.prediction_history, data.prediction.max_test_score)}
      </section>
      <section class="panel weak-panel"><div class="section-heading"><div><h2>Зоны внимания</h2><p>Темы с ошибками</p></div></div>
        <div class="weak-list">${data.weak_topics.length ? data.weak_topics.map((item) => `<article class="weak-item"><div><b>${item.short_title}</b><span>${item.correct} / ${item.attempts} · ${percent(item.mastery)}</span></div><span class="content-links"><a href="${item.theory_href}" data-open-theory="${item.theory_id}">Теория</a><a href="${item.practice_href}" data-open-task="${state.tasks.find((task) => task.topic_id === item.topic_id).id}">Практика</a></span></article>`).join("") : `<div class="empty-state compact">${data.summary.attempts ? "Тем с ошибками пока нет." : "Сначала решите несколько заданий."}</div>`}</div>
      </section>
      <section class="panel mastery-panel"><div class="section-heading"><div><h2>Результаты по темам</h2></div></div>
        <div class="mastery-list">${data.topics.map((item) => `<div class="mastery-item" style="--topic-color:${item.accent}"><div><b>${item.short_title}</b><span>${percent(item.mastery)} · ${item.attempts} попыток</span></div><div class="mini-track"><i style="width:${item.mastery ?? 0}%;background:${item.accent}"></i></div><span class="content-links"><a href="${item.theory_href}" data-open-theory="${item.theory_id}">Теория</a><a href="${item.practice_href}" data-open-task="${state.tasks.find((task) => task.topic_id === item.topic_id).id}">Практика</a></span></div>`).join("")}</div>
      </section>
      <section class="panel plan-panel"><div class="section-heading"><div><h2>Индивидуальный план</h2><p>Что повторить дальше</p></div></div>
        <div class="plan-list">${data.individual_plan.length ? data.individual_plan.map((item) => `<article class="plan-item"><i class="plan-dot"></i><span><b>${item.title}</b><small>${item.reason}</small><span class="content-links"><a href="${item.theory_href}" data-open-theory="${item.theory_id}">Теория</a><a href="${item.practice_href}" data-open-task="${item.task_id}">Практика</a></span></span><time>${formatDate(item.due_date)}</time></article>`).join("") : `<div class="empty-state compact">План появится после подтверждённой ошибки.</div>`}</div>
      </section>
    </div>`;
  bindContentLinks();
}

function riskLabel(risk) {
  return { stable: "Стабильно", attention: "Внимание", critical: "Риск" }[risk];
}

function renderAdmin() {
  const admin = state.admin;
  const usersRows = state.adminUsers.length ? state.adminUsers.map((user) => `<tr><td><b>${escapeHtml(user.name)}</b></td><td>${user.attempts}</td><td>${user.accuracy}%</td><td>${user.primary_result ?? "—"}</td><td>${formatDateTime(user.activity)}</td><td><span class="status-chip ${user.risk}">${riskLabel(user.risk)}</span></td></tr>`).join("") : `<tr><td colspan="6"><div class="empty-state compact">Пока нет ни одной реальной попытки.</div></td></tr>`;
  view.innerHTML = `${pageHeader("Роль администратора", "Панель управления", "Метрики пользователей считаются только по фактическим решениям.", '<button class="primary-button" id="add-content">+ Добавить материал</button>')}
    <section class="admin-banner"><div><h2>Учебный контур работает штатно</h2><p>Версия контента ${admin.system.content_version} · очередь фоновых задач ${admin.system.queue}</p></div><span class="status-ok"><i></i> API доступен</span></section>
    <section class="section"><div class="analytics-grid">
      <article class="metric-card"><small>Сессий с решениями</small><b>${admin.metrics.students}</b></article>
      <article class="metric-card"><small>Активны сегодня</small><b>${admin.metrics.active_today}</b></article>
      <article class="metric-card"><small>Решений сегодня</small><b>${admin.metrics.attempts_today}</b></article>
      <article class="metric-card"><small>Средний первичный результат</small><b>${admin.metrics.average_primary_result ?? "—"}</b></article>
    </div></section>
    <section class="section two-column">
      <div class="panel"><div class="section-heading"><div><h2>Реальные учебные сессии</h2><p>Строка появляется после первого решения</p></div></div><div class="table-scroll"><table class="admin-table"><thead><tr><th>Сессия</th><th>Попыток</th><th>Точность</th><th>Первичные</th><th>Активность</th><th>Статус</th></tr></thead><tbody>${usersRows}</tbody></table></div></div>
      <div class="panel"><div class="section-heading"><div><h2>Готовность контента</h2><p>Покрытие 19 позиций КИМ</p></div></div>
        <div class="forecast-number" style="font-size:62px">${admin.content.coverage_percent}<small>%</small></div>
        <div class="mini-track" style="height:8px"><i style="width:${admin.content.coverage_percent}%;background:var(--teal)"></i></div>
        <p class="data-note">${admin.content.tasks_published} из ${admin.content.tasks_total} заданий опубликованы · ${admin.content.theory_chapters} конспектов теории.</p>
      </div>
    </section>
    <section class="section panel"><div class="section-heading"><div><h2>Банк заданий</h2><p>Публикация управляется без удаления данных</p></div><span class="tag">ФИПИ-2026 · адаптировано</span></div>
      <div class="table-scroll"><table class="admin-table"><thead><tr><th>№</th><th>Название</th><th>Код</th><th>Сложность</th><th>Баллы</th><th>Публикация</th></tr></thead><tbody>
        ${state.adminTasks.map((task) => `<tr><td>${task.exam_number}</td><td><b>${task.title}</b></td><td>${task.codifier_code}</td><td>${difficultyLabel(task.difficulty)}</td><td>${task.max_primary_score}</td><td><button class="toggle ${task.published ? "on" : ""}" data-toggle-task="${task.id}" aria-label="Изменить публикацию"><i></i></button></td></tr>`).join("")}
      </tbody></table></div>
    </section>`;
  document.querySelector("#add-content").addEventListener("click", () => toast("Редактор материалов пока не подключён."));
  document.querySelectorAll("[data-toggle-task]").forEach((button) => button.addEventListener("click", () => toggleTask(button.dataset.toggleTask)));
}

async function toggleTask(taskId) {
  const task = state.adminTasks.find((item) => item.id === taskId);
  try {
    const updated = await request(`/admin/tasks/${taskId}/status`, {
      method: "PATCH", body: JSON.stringify({ published: !task.published }),
    });
    Object.assign(task, updated);
    state.admin = await request("/admin/dashboard");
    renderAdmin();
    toast(updated.published ? "Задание опубликовано" : "Задание снято с публикации");
  } catch (error) { toast(error.message); }
}

function bindGoButtons() {
  document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => goTo(button.dataset.go)));
}

function bindContentLinks() {
  document.querySelectorAll("[data-open-task], [data-open-theory], [data-roadmap-topic]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
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
  if (!state.theory.some((chapter) => chapter.id === theoryId)) return;
  state.focusTheory = theoryId;
  goTo("theory");
  requestAnimationFrame(() => document.querySelector(`#theory-${CSS.escape(theoryId)}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
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
    activeItem.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }
}

function goTo(page) {
  if (page === "practice" || page === "theory") page = "lessons";
  state.page = page;
  window.location.hash = page === "dashboard" ? "" : page;
  setActiveNav();
  render();
  view.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function render() {
  const pages = {
    dashboard: renderDashboard, roadmap: renderRoadmap, lessons: renderLessons,
    homework: renderHomework, analytics: renderAnalytics, admin: renderAdmin,
  };
  (pages[state.page] || renderDashboard)();
}

function toggleRole() {
  state.role = state.role === "student" ? "admin" : "student";
  const isAdmin = state.role === "admin";
  document.querySelectorAll(".admin-only").forEach((item) => item.classList.toggle("hidden", !isAdmin));
  document.querySelector("#role-name").textContent = isAdmin ? "Администратор" : "Ученик";
  document.querySelector("#role-label").textContent = isAdmin ? "Режим управления" : "Текущая сессия";
  document.querySelector(".avatar").textContent = isAdmin ? "АД" : "УЧ";
  goTo(isAdmin ? "admin" : "dashboard");
  toast(isAdmin ? "Включён интерфейс администратора" : "Возвращаемся в кабинет ученика");
}

document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => goTo(item.dataset.page)));
document.querySelector("#role-switch").addEventListener("click", toggleRole);

loadData().then(() => {
  updateHomeworkBadge();
  const hash = window.location.hash.slice(1);
  if (["roadmap", "lessons", "homework", "analytics", "admin"].includes(hash)) goTo(hash);
  else if (hash.startsWith("practice-") || hash.startsWith("theory-")) goTo("lessons");
  else {
    setActiveNav();
    render();
  }
}).catch((error) => {
  view.innerHTML = `<div class="error-card"><h2>Сайт запущен, но API не ответил</h2><p>${escapeHtml(error.message)}</p><button class="secondary-button" onclick="location.reload()">Повторить</button></div>`;
});
