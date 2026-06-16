const EXAMPLE_REPOS = [
  "sahilrw/research-agent",
  "mlabonne/llm-course",
  "psf/requests",
  "pallets/click",
  "pallets/flask",
  "fastapi/typer",
];

const $ = (sel) => document.querySelector(sel);

/* ---------- theme ---------- */
const SUN_ICON = '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M12 7a5 5 0 100 10 5 5 0 000-10zM12 1l1.8 3h-3.6zM12 23l-1.8-3h3.6zM1 12l3-1.8v3.6zM23 12l-3 1.8v-3.6zM4.2 4.2l3 1.2-1.8 1.8zM19.8 4.2l-1.2 3-1.8-1.8zM4.2 19.8l1.2-3 1.8 1.8zM19.8 19.8l-3-1.2 1.8-1.8z"/></svg>';
const MOON_ICON = '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M12 3a9 9 0 109 9 7 7 0 01-9-9z"/></svg>';

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("repo-assistant-theme", theme);
  $("#theme-toggle").innerHTML = theme === "dark" ? SUN_ICON : MOON_ICON;
}
applyTheme(localStorage.getItem("repo-assistant-theme") || "light");
$("#theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  applyTheme(next);
});

/* ---------- example chips ---------- */
const examplesEl = $("#examples");
EXAMPLE_REPOS.forEach((repo) => {
  const b = document.createElement("button");
  b.textContent = repo;
  b.addEventListener("click", () => { $("#repo-url").value = `https://github.com/${repo}`; });
  examplesEl.appendChild(b);
});

/* ---------- terminal rendering ---------- */
const KINDS = { "$": "cmd", ">": "run", "+": "ok", "✓": "done" };
let termLines = [];

function renderTerminal() {
  const body = $("#terminal-body");
  body.innerHTML = "";
  termLines.forEach((line, idx) => {
    const pfx = line[0];
    let rest = line.slice(1).trim();
    const kind = KINDS[pfx] || "run";
    for (const tok of ["ok", "paid", "ready"]) {
      if (rest.endsWith(" " + tok)) {
        rest = rest.slice(0, -tok.length) + `<span class="t-status">${tok}</span>`;
      }
    }
    const cursor = idx === termLines.length - 1 ? '<span class="cursor"></span>' : "";
    const div = document.createElement("div");
    div.className = `tline ln-${kind}`;
    div.innerHTML = `<span class="t-pfx">${pfx}</span> <span class="t-text">${rest}${cursor}</span>`;
    body.appendChild(div);
  });
}

function pushStatus(line) {
  if (!line) return;
  const last = termLines[termLines.length - 1];
  if (last && last.startsWith("> embedding") && line.startsWith("> embedding")) {
    termLines[termLines.length - 1] = line;
  } else {
    termLines.push(line);
  }
  renderTerminal();
}

termLines = ["> idle · no repository indexed yet"];
renderTerminal();

/* ---------- ingest ---------- */
$("#ingest-btn").addEventListener("click", ingest);
$("#repo-url").addEventListener("keydown", (e) => { if (e.key === "Enter") ingest(); });

async function ingest() {
  const url = $("#repo-url").value.trim();
  termLines = [];
  renderTerminal();
  try {
    const res = await fetch("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n");
      buffer = parts.pop();
      parts.forEach((p) => pushStatus(p));
    }
    if (buffer) pushStatus(buffer);
  } catch (e) {
    pushStatus(`> error · ${e}`);
  }
  loadSuggestions();
}

/* ---------- suggestions (typewriter placeholder) ---------- */
let twTimer = null;

function startTypewriter(questions) {
  const input = $("#question");
  if (twTimer) clearTimeout(twTimer);
  if (!questions.length) return;
  let i = 0, j = 0, deleting = false;
  const step = () => {
    const cur = questions[i];
    j = deleting ? j - 1 : j + 1;
    input.setAttribute("placeholder", cur.slice(0, Math.max(0, j)) + " ▌");
    let delay = deleting ? 28 : 55;
    if (!deleting && j >= cur.length) { deleting = true; delay = 1600; }
    else if (deleting && j <= 0) { deleting = false; i = (i + 1) % questions.length; delay = 350; }
    twTimer = setTimeout(step, delay);
  };
  step();
}

async function loadSuggestions() {
  try {
    const res = await fetch("/api/suggestions");
    const data = await res.json();
    startTypewriter(data.questions || []);
  } catch (e) { /* keep default placeholder */ }
}
loadSuggestions();

/* ---------- chat ---------- */
const chatEl = $("#chat");
const messages = [];

const EMPTY_PHRASES = [
  "Ask a question about the indexed repository.",
  "Repository insights will appear here.",
  "Answers from your codebase will be displayed here.",
  "Query the repository and view results here.",
  "Ask anything about the codebase.",
  "Search, analyze, and understand your repository here.",
  "Repository answers and references will appear here.",
  "Your codebase assistant is ready. Ask a question.",
  "Waiting for your repository query…",
  "Index a repository and ask a question to get started.",
];
const EMPTY_PHRASE = EMPTY_PHRASES[Math.floor(Math.random() * EMPTY_PHRASES.length)];

function renderChat(streamingCursor) {
  chatEl.innerHTML = "";
  if (!messages.length) {
    const hint = document.createElement("div");
    hint.className = "chat-empty";
    hint.textContent = EMPTY_PHRASE;
    chatEl.appendChild(hint);
    return;
  }
  messages.forEach((m, idx) => {
    const div = document.createElement("div");
    div.className = `msg ${m.role}`;
    const isLastBot = idx === messages.length - 1 && m.role === "bot";
    if (m.role === "bot") {
      const text = m.content + (isLastBot && streamingCursor ? " ▌" : "");
      div.innerHTML = marked.parse(text);
    } else {
      div.textContent = m.content;
    }
    chatEl.appendChild(div);
  });
}

renderChat(false);

$("#ask-btn").addEventListener("click", ask);
$("#question").addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });

async function ask() {
  const input = $("#question");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";

  messages.push({ role: "user", content: question });
  const bot = { role: "bot", content: "_generating…_" };
  messages.push(bot);
  renderChat(false);

  let target = "";
  let shown = 0;
  let streamDone = false;
  bot.content = "";

  const tick = setInterval(() => {
    if (shown < target.length) {
      shown = Math.min(target.length, shown + 2);
      bot.content = target.slice(0, shown);
      renderChat(true);
    } else if (streamDone) {
      clearInterval(tick);
      renderChat(false);
    }
  }, 20);

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      target += decoder.decode(value, { stream: true });
    }
  } catch (e) {
    target += `\n\n[error: ${e}]`;
  }
  streamDone = true;
}

/* ---------- footer scramble effect ---------- */
const SCRAMBLE_CHARS = "!<>-_\\/[]{}=+*^?#01x";
document.querySelectorAll("#site-footer a.scramble").forEach((el) => {
  const original = el.textContent;
  el.addEventListener("mouseenter", () => {
    let frame = 0;
    const total = 16;
    el.classList.add("scrambling");
    clearInterval(el._scrambleTimer);
    el._scrambleTimer = setInterval(() => {
      const reveal = Math.floor((frame / total) * original.length);
      let out = "";
      for (let i = 0; i < original.length; i++) {
        const c = original[i];
        if (c === " " || c === "@" || i < reveal) out += c;
        else out += SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
      }
      el.textContent = out;
      frame++;
      if (frame > total) {
        clearInterval(el._scrambleTimer);
        el.textContent = original;
        el.classList.remove("scrambling");
      }
    }, 28);
  });
});
