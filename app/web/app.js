const API = "/api/v1/exam/math-profile";
const sessionId = "local-student";

const state = {
  role: "student",
  page: "dashboard",
  overview: null,
  tasks: [],
  theory: [],
  analytics: null,
  roadmap: null,
  admin: null,
  adminUsers: [],
  adminTasks: [],
  currentTask: 0,
  practiceFilter: "all",
  focusTheory: null,
};

const view = document.querySelector("#view");
const sidebar = document.querySelector("#sidebar");

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Не удалось получить данные");
  return payload.data;
}

async function loadData() {
  const [overview, tasks, theory, analytics, roadmap, admin, adminUsers, adminTasks] =
    await Promise.all([
      request("/overview"), request("/tasks"), request("/theory"),
      request(`/analytics?session_id=${sessionId}`),
      request(`/roadmap?session_id=${sessionId}`), request("/admin/dashboard"),
      request("/admin/users"), request("/admin/tasks"),
    ]);
  Object.assign(state, { overview, tasks, theory, analytics, roadmap, admin, adminUsers, adminTasks });
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
    <div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p>${description}</p></div>
    ${action ? `<div class="header-action">${action}</div>` : ""}
  </header>`;
}

function topicCard(topic) {
  const metric = state.analytics.topics.find((item) => item.topic_id === topic.id);
  const symbols = { geometry: "△", vectors: "→", probability: "P", equations: "x", functions: "f", calculus: "∫", applied: "%", number_theory: "№" };
  const firstTask = state.tasks.find((task) => task.topic_id === topic.id);
  return `<article class="topic-card" style="--topic-color:${topic.accent}">
    <div class="topic-top"><span class="topic-icon">${symbols[topic.id]}</span><span class="topic-score">${percent(metric.mastery)}</span></div>
    <h3>${topic.short_title}</h3><p>${topic.description}</p>
    <div class="mini-track"><i style="width:${metric.mastery ?? 0}%"></i></div>
    <div class="content-links"><a href="#theory-${metric.theory_id}" data-open-theory="${metric.theory_id}">Теория</a><a href="#practice-${firstTask.id}" data-open-task="${firstTask.id}">Практика №${firstTask.exam_number}</a></div>
  </article>`;
}

function renderForecastCard(prediction) {
  const coverage = Math.round(prediction.covered_task_types / prediction.required_task_types * 100);
  if (prediction.available) {
    return `<aside class="forecast-card">
      <div class="card-kicker"><span>Полная диагностика</span><span class="model-badge">реальные ответы</span></div>
      <div class="forecast-number">${prediction.predicted_primary_score}<small> / 32 первичных</small></div>
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

function renderDashboard() {
  const analytics = state.analytics;
  const prediction = analytics.prediction;
  const hasAttempts = analytics.summary.attempts > 0;
  const next = analytics.individual_plan;
  const maxDay = Math.max(1, ...analytics.week_activity.map((item) => item.attempts));
  view.innerHTML = `
    <div class="hero-grid">
      <section class="hero-card">
        <div class="hero-copy">
          <p class="eyebrow">Ваши реальные результаты</p>
          <h1>${hasAttempts ? "Продолжим подготовку." : "Начните диагностику."}</h1>
          <p>${hasAttempts ? `Учтено ${analytics.summary.attempts} решений. Все показатели ниже рассчитаны только по вашим ответам.` : "Решите первое задание — до этого момента аналитика и прогноз останутся пустыми."}</p>
          <div class="hero-actions"><button class="primary-button" data-go="practice">${hasAttempts ? "Продолжить практику" : "Решить первое задание"} →</button></div>
        </div>
        <div class="hero-visual" aria-hidden="true">
          <div class="formula-orbit"></div><span class="formula f1">P(A)</span>
          <span class="formula f2">x² + y²</span><span class="formula f3">f′(x)</span><span class="pencil-line"></span>
        </div>
      </section>
      ${renderForecastCard(prediction)}
    </div>

    <section class="section">
      <div class="section-heading"><div><h2>Карта знаний</h2><p>Проценты появляются только после реальных попыток</p></div><button class="text-button" data-go="analytics">Вся аналитика →</button></div>
      <div class="topic-grid">${state.overview.topics.slice(0, 4).map(topicCard).join("")}</div>
    </section>

    <section class="section two-column">
      <div class="panel">
        <div class="section-heading"><div><h2>Ближайший план</h2><p>Только темы, где уже были ошибки</p></div><button class="text-button" data-go="roadmap">Маршрут →</button></div>
        <div class="next-list">${next.length ? next.map((item) => `<article class="next-item">
          <span class="next-date">${formatDate(item.due_date)}</span>
          <span><b>${item.title}</b><small>${item.action}</small><span class="content-links"><a href="${item.theory_href}" data-open-theory="${item.theory_id}">Теория</a><a href="${item.practice_href}" data-open-task="${item.task_id}">Практика</a></span></span><em>${percent(item.mastery)}</em>
        </article>`).join("") : `<div class="empty-state compact">${hasAttempts ? "По текущим ответам тем с ошибками нет." : "План повторения появится после первой ошибки."}</div>`}</div>
      </div>
      <div class="panel">
        <div class="section-heading"><div><h2>Практика за 7 дней</h2><p>Количество ваших решений по дням</p></div></div>
        <div class="week-bars">${analytics.week_activity.map((item) => `<span title="${formatDate(item.date)} · решений: ${item.attempts}" style="--bar-height:${item.attempts ? Math.max(18, item.attempts / maxDay * 100) : 8}%"><i></i><small>${item.attempts}</small></span>`).join("")}</div>
        <p class="data-note">${analytics.summary.attempts} попыток · ${analytics.summary.study_minutes} минут практики. Здесь нет демонстрационных значений.</p>
      </div>
    </section>`;
  bindGoButtons();
  bindContentLinks();
}

function renderRoadmap() {
  const roadmap = state.roadmap;
  view.innerHTML = `${pageHeader("Персональный маршрут", "Темы и задания ЕГЭ", roadmap.principle,
    '<button class="primary-button" data-go="practice">Перейти к практике →</button>')}
    <section class="roadmap-summary"><div><h2>Покрытие программы</h2><p>Прогресс означает число типов заданий, по которым есть хотя бы одна реальная попытка.</p></div>
      <div class="roadmap-progress-big">${roadmap.covered_task_types}<small>из ${roadmap.total_task_types} типов</small></div></section>
    <div class="roadmap-list">${roadmap.stages.map((stage) => `<article class="stage-card ${stage.state}">
      <span class="stage-number">${stage.state === "completed" ? "✓" : stage.number}</span>
      <div class="stage-main"><h3>${stage.title}</h3><p>${stage.subtitle} · ${stage.weeks}</p>
        <div class="roadmap-topics">${stage.topics.map((topic) => `<div class="roadmap-topic"><span><b>${topic.title}</b><small>Задания ${topic.task_numbers.map((number) => `№${number}`).join(", ")} · результат ${percent(topic.mastery)}</small></span><span class="content-links"><a href="${topic.theory_href}" data-open-theory="${topic.theory_id}">Теория</a><a href="${topic.practice_href}" data-open-task="${stage.tasks.find((task) => topic.task_numbers.includes(task.exam_number)).id}">Практика</a></span></div>`).join("")}</div>
        <div class="task-link-row">${stage.tasks.map((task) => `<a href="${task.href}" data-open-task="${task.id}" class="task-link ${task.difficulty === "expert" ? "complex" : ""}">№${task.exam_number} · ${task.title}</a>`).join("")}</div>
      </div>
      <div class="stage-meta"><b>${stage.covered_task_types}/${stage.task_types}</b><small>${stage.state === "current" ? "текущий этап" : stage.state === "completed" ? "пройден" : "впереди"}</small></div>
    </article>`).join("")}</div>`;
  bindGoButtons();
  bindContentLinks();
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
          ${[["all","Все"],["basic","База"],["standard","Средние"],["advanced","Повышенные"],["expert","Сложные"]].map(([value,label]) => `<button class="filter-chip ${state.practiceFilter === value ? "active" : ""}" data-filter="${value}">${label}</button>`).join("")}
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

function renderHistory(history) {
  if (!history.length) return `<div class="empty-state">График появится после первого решённого задания.</div>`;
  const step = history.length === 1 ? 0 : 504 / (history.length - 1);
  const points = history.map((item, index) => `${28 + index * step},${218 - item.score * 1.72}`).join(" ");
  const areaPoints = `28,218 ${points} ${28 + (history.length - 1) * step},218`;
  return `<svg class="forecast-chart" viewBox="0 0 560 235" role="img" aria-label="Динамика фактической точности">
      ${[46,89,132,175,218].map((y) => `<line class="grid" x1="28" y1="${y}" x2="532" y2="${y}"></line>`).join("")}
      <polygon class="area" points="${areaPoints}"></polygon><polyline class="line" points="${points}"></polyline>
      ${history.map((item, index) => `<circle class="dot" cx="${28 + index * step}" cy="${218 - item.score * 1.72}" r="5"></circle>`).join("")}
    </svg><div class="chart-labels">${history.map((item) => `<span>${item.label}<br><b>${item.score}%</b></span>`).join("")}</div>`;
}

function renderAnalytics() {
  const data = state.analytics;
  const prediction = data.prediction;
  view.innerHTML = `${pageHeader("Результаты", "Аналитика по вашим ответам", "Никаких стартовых процентов: только попытки, точность, ошибки и покрытие типов заданий.")}
    <div class="analytics-grid">
      <article class="metric-card"><small>Попыток</small><b>${data.summary.attempts}</b></article>
      <article class="metric-card"><small>Точность</small><b>${percent(data.summary.accuracy)}</b></article>
      <article class="metric-card"><small>Типов пройдено</small><b>${prediction.covered_task_types}<span class="metric-suffix"> / ${prediction.required_task_types}</span></b></article>
      <article class="metric-card"><small>Результат диагностики</small><b>${prediction.available ? prediction.predicted_primary_score : "—"}<span class="metric-suffix"> / 32</span></b></article>

      <section class="panel chart-panel"><div class="section-heading"><div><h2>Динамика точности</h2><p>Накопительная точность после каждой реальной попытки</p></div><span class="model-badge">фактические ответы</span></div>
        ${renderHistory(data.history)}
      </section>
      <section class="panel weak-panel"><div class="section-heading"><div><h2>Зоны внимания</h2><p>Только темы, где уже были ошибки</p></div></div>
        <div class="weak-list">${data.weak_topics.length ? data.weak_topics.map((item) => `<article class="weak-item"><div><b>${item.short_title}</b><span>${percent(item.mastery)}</span></div><p>Точность ${item.accuracy}% на ${item.attempts} попытках</p><span class="content-links"><a href="${item.theory_href}" data-open-theory="${item.theory_id}">Теория</a><a href="${item.practice_href}" data-open-task="${state.tasks.find((task) => task.topic_id === item.topic_id).id}">Практика</a></span></article>`).join("") : `<div class="empty-state compact">${data.summary.attempts ? "Тем с ошибками пока нет." : "Сначала решите несколько заданий."}</div>`}</div>
      </section>
      <section class="panel mastery-panel"><div class="section-heading"><div><h2>Результаты по темам</h2><p>Точность без сглаживания и стартовых значений</p></div></div>
        <div class="mastery-list">${data.topics.map((item) => `<div class="mastery-item" style="--topic-color:${item.accent}"><div><b>${item.short_title}</b><span>${percent(item.mastery)} · ${item.attempts} попыток</span></div><div class="mini-track"><i style="width:${item.mastery ?? 0}%;background:${item.accent}"></i></div><span class="content-links"><a href="${item.theory_href}" data-open-theory="${item.theory_id}">Теория</a><a href="${item.practice_href}" data-open-task="${state.tasks.find((task) => task.topic_id === item.topic_id).id}">Практика</a></span></div>`).join("")}</div>
      </section>
      <section class="panel plan-panel"><div class="section-heading"><div><h2>Индивидуальный план</h2><p>Повторение только подтверждённых ошибок</p></div></div>
        <div class="plan-list">${data.individual_plan.length ? data.individual_plan.map((item) => `<article class="plan-item"><i class="plan-dot"></i><span><b>${item.title}</b><small>${item.action}<br>${item.reason}</small><span class="content-links"><a href="${item.theory_href}" data-open-theory="${item.theory_id}">Теория</a><a href="${item.practice_href}" data-open-task="${item.task_id}">Практика</a></span></span><time>${formatDate(item.due_date)}</time></article>`).join("") : `<div class="empty-state compact">План появится после подтверждённой ошибки.</div>`}</div>
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
  document.querySelectorAll("[data-open-task]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
    window.location.hash = `practice-${link.dataset.openTask}`;
    openPracticeTask(link.dataset.openTask);
  }));
  document.querySelectorAll("[data-open-theory]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
    window.location.hash = `theory-${link.dataset.openTheory}`;
    openTheory(link.dataset.openTheory);
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

function setActiveNav() {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.page === state.page));
}

function goTo(page) {
  state.page = page;
  setActiveNav();
  sidebar.classList.remove("open");
  render();
  view.focus({ preventScroll: true });
  if (!window.location.hash.startsWith("#theory-") && !window.location.hash.startsWith("#practice-")) window.scrollTo({ top: 0, behavior: "smooth" });
}

function render() {
  const pages = {
    dashboard: renderDashboard, roadmap: renderRoadmap, practice: renderPractice,
    theory: renderTheory, analytics: renderAnalytics, admin: renderAdmin,
  };
  (pages[state.page] || renderDashboard)();
}

function toggleRole() {
  state.role = state.role === "student" ? "admin" : "student";
  const isAdmin = state.role === "admin";
  document.querySelectorAll(".admin-only").forEach((item) => item.classList.toggle("hidden", !isAdmin));
  document.querySelector("#role-name").textContent = isAdmin ? "Мария" : "Алексей";
  document.querySelector("#role-label").textContent = isAdmin ? "Администратор контента" : "Ученик · 11 класс";
  document.querySelector(".avatar").textContent = isAdmin ? "МВ" : "АК";
  goTo(isAdmin ? "admin" : "dashboard");
  toast(isAdmin ? "Включён интерфейс администратора" : "Возвращаемся в кабинет ученика");
}

document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => goTo(item.dataset.page)));
document.querySelector("#role-switch").addEventListener("click", toggleRole);
document.querySelector("#mobile-menu").addEventListener("click", () => sidebar.classList.toggle("open"));

loadData().then(() => {
  const hash = window.location.hash.slice(1);
  if (hash.startsWith("practice-")) openPracticeTask(hash.slice("practice-".length));
  else if (hash.startsWith("theory-")) openTheory(hash.slice("theory-".length));
  else render();
}).catch((error) => {
  view.innerHTML = `<div class="error-card"><h2>Сайт запущен, но API не ответил</h2><p>${escapeHtml(error.message)}</p><button class="secondary-button" onclick="location.reload()">Повторить</button></div>`;
});
