const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const vm = require("node:vm");
const { join } = require("node:path");

function app({ fetch, blockedStorage = false } = {}) {
  const elements = new Map();
  const storage = new Map();
  const element = (selector) => {
    if (!elements.has(selector)) {
      const classes = new Set();
      elements.set(selector, {
        isConnected: true, innerHTML: "", textContent: "", disabled: false,
        classList: { add: (v) => classes.add(v), remove: (v) => classes.delete(v),
          contains: (v) => classes.has(v), toggle: (v, on) => on ? classes.add(v) : classes.delete(v) },
        setAttribute() {}, removeAttribute() {}, addEventListener() {}, focus() {}, reset() {},
        replaceChildren() { this.innerHTML = ""; }, contains: () => false,
      });
    }
    return elements.get(selector);
  };
  const context = vm.createContext({
    document: { querySelector: element, querySelectorAll: () => [], addEventListener() {} },
    sessionStorage: {
      getItem: (key) => { if (blockedStorage) throw new Error("blocked"); return storage.get(key); },
      setItem: (key, value) => { if (blockedStorage) throw new Error("blocked"); storage.set(key, value); },
      removeItem: (key) => { if (blockedStorage) throw new Error("blocked"); storage.delete(key); },
    },
    window: { location: { origin: "http://localhost", hash: "" }, matchMedia: () => ({ matches: false }), addEventListener() {} },
    ResizeObserver: class { observe() {} }, URL, AbortSignal, fetch, setTimeout,
  });
  const source = readFileSync(join(__dirname, "../../app/web/app.js"), "utf8");
  vm.runInContext(source.replace(/restoreSession\(\);\s*$/, ""), context);
  return { run: (code) => vm.runInContext(code, context), element, storage };
}
const response = (status, data) => ({ status, ok: status < 400, json: async () => ({ data }) });
const tokens = { access_token: "access", refresh_token: "refresh" };

test("hostile task text and javascript source URLs stay inert", () => {
  const a = app();
  a.run(`state.aiStatus = { configured: false };`);
  const html = a.run(`renderPracticeStep({ topic: { short_title: '<img src=x onerror=alert(1)>' },
    practice: { total_tasks: 1, current_task_number: 1, attempted_tasks: 0 },
    practice_task: { title: '<script>alert(1)</script>', prompt: '<img src=x onerror=alert(1)>',
      exam_number: 2, difficulty: 'basic', codifier_code: '" onmouseover="alert(1)',
      lesson_task_key: 'qa', source: { url: 'javascript:alert(1)', label: '<svg onload=alert(1)>' } } })`);
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(!html.includes('codifier_code="'));
});

test("headings escape API text and links reject unsafe schemes", () => {
  const a = app();
  assert.ok(a.run(`pageHeader('<script>', '<svg>')`).includes("&lt;script&gt;"));
  for (const url of ["javascript:alert(1)", "data:text/html,x", "https://user:pass@example.test"]) {
    assert.equal(a.run(`safeUrl(${JSON.stringify(url)})`), "#");
  }
  assert.equal(a.run(`safeUrl('#theory-vectors')`), "http://localhost/#theory-vectors");
});

test("refresh arriving after logout cannot restore credentials or private data", async () => {
  let release;
  const a = app({ fetch: () => new Promise(resolve => { release = resolve; }) });
  a.run(`persistTokens(${JSON.stringify(tokens)}); state.auth.user = { id: 'one' }; state.lesson = { private: true };`);
  const pending = a.run("refreshTokens()");
  a.run("endLocalSession()");
  release(response(200, { access_token: "new-access", refresh_token: "new-refresh" }));
  assert.equal(await pending, false);
  assert.equal(a.run("state.auth.accessToken"), null);
  assert.equal(a.run("state.auth.refreshToken"), null);
  assert.equal(a.run("state.lesson"), null);
  assert.equal(a.storage.size, 0);
});

test("late personal API response is rejected after changing account", async () => {
  let release;
  const a = app({ fetch: () => new Promise(resolve => { release = resolve; }) });
  a.run(`persistTokens(${JSON.stringify(tokens)})`);
  const pending = a.run(`request('/analytics')`);
  a.run("endLocalSession()");
  release(response(200, { private: "old account" }));
  await assert.rejects(pending, error => error.silent === true);
});

test("repeated 401 after a successful refresh clears the session", async () => {
  const replies = [response(401), response(200, tokens), response(401)];
  const a = app({ fetch: async () => replies.shift() });
  a.run(`persistTokens(${JSON.stringify(tokens)})`);
  await assert.rejects(a.run(`request('/analytics')`), error => error.silent === true);
  assert.equal(a.run("state.auth.accessToken"), null);
  assert.equal(replies.length, 0);
});

test("parallel unauthorized requests share one refresh", async () => {
  let refreshCalls = 0;
  const a = app({ fetch: async (url, options) => {
    if (url.endsWith("/refresh")) { refreshCalls++; return response(200, { access_token: "new", refresh_token: "new-r" }); }
    return options.headers.Authorization === "Bearer new" ? response(200, { ok: true }) : response(401);
  } });
  a.run(`persistTokens(${JSON.stringify(tokens)})`);
  await a.run(`Promise.all([request('/analytics'), request('/dashboard')])`);
  assert.equal(refreshCalls, 1);
});

test("blocked storage does not prevent in-memory login and logout", () => {
  const a = app({ blockedStorage: true });
  a.run(`persistTokens(${JSON.stringify(tokens)})`);
  assert.equal(a.run("state.auth.accessToken"), "access");
  a.run("endLocalSession()");
  assert.equal(a.run("state.auth.accessToken"), null);
});

test("network failure has an actionable Russian message", async () => {
  const a = app({ fetch: async () => { throw new TypeError("Failed to fetch"); } });
  await assert.rejects(a.run(`request('/analytics')`), /Проверьте подключение/);
});


test("analytics remains usable when a topic task is unpublished", () => {
  const a = app();
  a.run(`state.tasks = []; state.analytics = {
    prediction: { available: false, covered_task_types: 0, required_task_types: 19, max_test_score: 100 },
    prediction_history: [], summary: { attempts: 1, correct: 0 }, weak_topics: [], individual_plan: [],
    topics: [{ short_title: 'Векторы', topic_id: 'vectors', attempts: 1, mastery: 0,
      accent: '#267468', theory_id: 'vectors', theory_href: '#theory-vectors', practice_href: '#lessons' }]
  }; renderAnalytics();`);
  assert.ok(a.element('#view').innerHTML.includes('Векторы'));
  assert.ok(a.element('#view').innerHTML.includes('data-open-task=""'));
});


test("late hint does not write into a different screen", async () => {
  let release;
  const a = app({ fetch: () => new Promise(resolve => { release = resolve; }) });
  a.run(`state.lesson = { unit_id: 'vectors', practice_task: { lesson_task_key: 'first' } };`);
  const pending = a.run("requestAIHint()");
  a.element('#ai-hint-button').isConnected = false;
  release(response(200, { level: 1, hint: "Old screen", focus: "Tip", self_check: "Check" }));
  await pending;
  assert.equal(a.element('#ai-hint-list').innerHTML, "");
  assert.equal(a.run("state.aiHints.first.length"), 1);
});
