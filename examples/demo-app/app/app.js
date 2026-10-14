// Acme Tasks: a tiny sample app for filmwright's demo mode. Data lives in this tab only (sessionStorage).
const SEED = [
  { id: 1, title: "Draft the launch checklist", owner: "Maya", done: false },
  { id: 2, title: "Review the onboarding emails", owner: "Raj", done: true },
  { id: 3, title: "Book the team retro", owner: "Lee", done: false },
];
const load = () => { try { return JSON.parse(sessionStorage.getItem("tasks")) || SEED; } catch { return SEED; } };
let tasks = load(), filter = "all";
const save = () => sessionStorage.setItem("tasks", JSON.stringify(tasks));
const $ = (s) => document.querySelector(s);

function toast(text) {
  const t = $("#toast");
  t.textContent = text; t.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => { t.hidden = true; }, 2200);
}

function render() {
  const list = $("#list");
  list.innerHTML = "";
  tasks.filter((t) => filter === "all" || (filter === "done") === t.done).forEach((t) => {
    const li = document.createElement("li");
    li.className = "item" + (t.done ? " done" : "");
    li.dataset.testid = "task";
    const box = document.createElement("input");
    box.type = "checkbox"; box.checked = t.done; box.setAttribute("aria-label", "Done: " + t.title);
    box.addEventListener("change", () => { t.done = box.checked; save(); render(); if (t.done) toast("Nice work. Task done."); });
    const title = document.createElement("span"); title.className = "t"; title.textContent = t.title;
    const owner = document.createElement("span"); owner.className = "owner"; owner.textContent = t.owner;
    li.append(box, title, owner);
    list.appendChild(li);
  });
  const open = tasks.filter((t) => !t.done).length;
  $("[data-testid=count]").textContent = `${open} open · ${tasks.length - open} done`;
}

document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  filter = b.dataset.filter;
  document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
  render();
}));

$("#add").addEventListener("submit", (e) => {
  e.preventDefault();
  const title = $("#title").value.trim();
  if (!title) return;
  tasks.push({ id: Date.now(), title, owner: $("#owner").value, done: false });
  save(); $("#title").value = ""; render(); toast("Task added");
});

// a tiny read-only API for `api` steps: GET /api/tasks.json is served as a static file
render();
