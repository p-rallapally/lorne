const STORAGE_KEY = "lorne-saved-events";
const state = {
  q: "", location: "", radius: "", startDate: "", endDate: "",
  sort: "date_asc", saved: loadSaved(),
};

const els = {
  tabs: document.querySelectorAll(".tab"), views: document.querySelectorAll(".view"),
  grid: document.getElementById("event-grid"), count: document.getElementById("result-count"),
  status: document.getElementById("status-region"), q: document.getElementById("q-input"),
  location: document.getElementById("location-input"), radius: document.getElementById("radius-select"),
  startDate: document.getElementById("start-date"), endDate: document.getElementById("end-date"),
  sort: document.getElementById("sort-select"), chips: document.querySelectorAll(".chip"),
  quickDates: document.querySelectorAll(".quick-date"), performerGrid: document.getElementById("performer-grid"),
  performerStatus: document.getElementById("performer-status"), performerCount: document.getElementById("performer-count"),
  savedGrid: document.getElementById("saved-grid"), savedStatus: document.getElementById("saved-status"),
  savedCount: document.getElementById("saved-count"),
};

let debounceTimer;
let requestToken = 0;

function eventKey(event) {
  return `${event.source_platform}:${event.event_id}`;
}

function loadSaved() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    return Object.fromEntries(
      Object.entries(saved).filter(([, event]) => ["current", "alumni"].includes(event.cast_status))
    );
  }
  catch { return {}; }
}

function persistSaved() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.saved));
  els.savedCount.textContent = Object.keys(state.saved).length;
}

function scheduleFetch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fetchEvents, 300);
}

async function fetchEvents() {
  if (state.radius && !state.location) {
    renderError("Enter a location to use distance search.");
    return;
  }
  const params = new URLSearchParams({ sort: state.sort, limit: "100" });
  if (state.q) params.set("q", state.q);
  if (state.location) params.set(state.radius ? "near" : "location", state.location);
  if (state.radius) params.set("radius", state.radius);
  if (state.startDate) params.set("start_date", state.startDate);
  if (state.endDate) params.set("end_date", state.endDate);

  const token = ++requestToken;
  renderLoading();
  try {
    const response = await fetch(`/api/events?${params}`);
    const data = await response.json();
    if (token !== requestToken) return;
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    renderEvents(data);
  } catch (error) {
    if (token !== requestToken) return;
    renderError(error instanceof TypeError ? "Couldn't reach the server. Try again." : error.message);
  }
}

function renderLoading() {
  els.status.hidden = false;
  els.status.className = "status status--loading";
  els.status.textContent = "Finding shows…";
  els.grid.hidden = true;
}

function renderError(message) {
  els.status.hidden = false;
  els.status.className = "status status--error";
  els.status.textContent = message;
  els.grid.hidden = true;
  els.count.textContent = "";
}

function renderEvents(data) {
  els.count.textContent = `${data.count} show${data.count === 1 ? "" : "s"}`;
  if (!data.events.length) {
    els.status.hidden = false;
    els.status.className = "status status--empty";
    els.status.textContent = "No shows match your filters. Try widening the search.";
    els.grid.hidden = true;
    return;
  }
  els.status.hidden = true;
  els.grid.hidden = false;
  els.grid.innerHTML = data.events.map(renderCard).join("");
  data.events.forEach(event => {
    const button = els.grid.querySelector(`[data-save-key="${eventKey(event)}"]`);
    if (button) button._event = event;
  });
}

function renderCard(event, index) {
  const key = eventKey(event);
  const { day, month, label } = formatDate(event.date);
  const badges = [];
  if (event.sold_out) badges.push('<span class="badge badge--sold-out">Sold out</span>');
  if (event.distance_miles != null) badges.push(`<span class="badge badge--distance">${event.distance_miles.toFixed(1)} mi away</span>`);
  return `<article class="card">
    <div class="card__top"><div class="card__date card__date--${event.cast_status}">
      <span class="card__month">${escapeHtml(month)}</span><span class="card__day">${escapeHtml(day)}</span>
    </div><span class="card__weekday">${escapeHtml(label)}</span></div>
    <div class="card__badges">${badges.join("")}</div>
    <h3 class="card__performer">${escapeHtml(event.performer)}</h3>
    <p class="card__venue">${escapeHtml(event.venue || "Venue TBA")}</p>
    <p class="card__location">${escapeHtml(event.location || "Location TBA")}</p>
    <div class="card__footer">
      <button class="save-button ${state.saved[key] ? "save-button--active" : ""}" type="button" data-save-key="${escapeHtml(key)}">${state.saved[key] ? "Saved ♥" : "Save ♡"}</button>
      <a class="card__link" href="${safeUrl(event.ticket_url)}" target="_blank" rel="noopener noreferrer">${event.sold_out ? "Details" : "Tickets"} ↗</a>
    </div>
  </article>`;
}

function formatDate(iso) {
  if (!iso) return { day: "?", month: "TBD", label: "Date TBA" };
  const parsed = new Date(`${iso.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return { day: "?", month: "TBD", label: iso };
  return {
    day: parsed.toLocaleDateString(undefined, { day: "2-digit" }),
    month: parsed.toLocaleDateString(undefined, { month: "short" }).toUpperCase(),
    label: parsed.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "short", day: "numeric" }),
  };
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
  } catch { return "#"; }
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

function computeQuickRange(range) {
  const today = new Date();
  const localISO = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  if (range === "weekend") {
    const saturday = new Date(today);
    saturday.setDate(today.getDate() + (6 - today.getDay() + 7) % 7);
    const sunday = new Date(saturday); sunday.setDate(saturday.getDate() + 1);
    return { start: localISO(today), end: localISO(sunday) };
  }
  if (range === "30days") {
    const end = new Date(today); end.setDate(today.getDate() + 30);
    return { start: localISO(today), end: localISO(end) };
  }
  return { start: "", end: "" };
}

function clearQuickDates() {
  els.quickDates.forEach(button => {
    button.classList.remove("quick-date--active");
    button.setAttribute("aria-pressed", "false");
  });
}

async function renderPerformers() {
  els.performerStatus.hidden = false;
  els.performerGrid.hidden = true;
  try {
    const response = await fetch("/api/performers");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to load performers");
    els.performerCount.textContent = `${data.count} performer${data.count === 1 ? "" : "s"}`;
    els.performerGrid.innerHTML = data.performers.map(item => `<button class="performer-card" type="button" data-performer="${escapeAttribute(item.performer)}"><strong>${escapeHtml(item.performer)}</strong><span>${item.upcoming_count} upcoming show${item.upcoming_count === 1 ? "" : "s"}</span></button>`).join("");
    els.performerStatus.hidden = true;
    els.performerGrid.hidden = false;
  } catch (error) {
    els.performerStatus.textContent = error.message;
    els.performerStatus.className = "status status--error";
  }
}

function renderSaved() {
  const events = Object.values(state.saved);
  els.savedCount.textContent = events.length;
  els.savedStatus.hidden = events.length > 0;
  els.savedGrid.hidden = events.length === 0;
  els.savedGrid.innerHTML = events.map(renderCard).join("");
}

function showView(name) {
  els.views.forEach(view => { view.hidden = view.id !== `${name}-view`; });
  els.tabs.forEach(tab => tab.classList.toggle("tab--active", tab.dataset.view === name));
  if (name === "performers") renderPerformers();
  if (name === "saved") renderSaved();
}

els.tabs.forEach(tab => tab.addEventListener("click", () => showView(tab.dataset.view)));
els.q.addEventListener("input", event => { state.q = event.target.value.trim(); scheduleFetch(); });
els.location.addEventListener("input", event => {
  state.location = event.target.value.trim();
  els.chips.forEach(chip => {
    const active = chip.dataset.location === state.location;
    chip.classList.toggle("chip--active", active); chip.setAttribute("aria-pressed", String(active));
  });
  scheduleFetch();
});
els.radius.addEventListener("change", event => { state.radius = event.target.value; fetchEvents(); });
els.startDate.addEventListener("change", event => { state.startDate = event.target.value; clearQuickDates(); fetchEvents(); });
els.endDate.addEventListener("change", event => { state.endDate = event.target.value; clearQuickDates(); fetchEvents(); });
els.sort.addEventListener("change", event => { state.sort = event.target.value; fetchEvents(); });

els.chips.forEach(chip => chip.addEventListener("click", () => {
  const active = chip.classList.contains("chip--active");
  els.chips.forEach(item => { item.classList.remove("chip--active"); item.setAttribute("aria-pressed", "false"); });
  if (!active) { chip.classList.add("chip--active"); chip.setAttribute("aria-pressed", "true"); }
  state.location = active ? "" : chip.dataset.location;
  els.location.value = state.location;
  fetchEvents();
}));

els.quickDates.forEach(button => button.addEventListener("click", () => {
  const active = button.classList.contains("quick-date--active");
  const range = active ? "all" : button.dataset.range;
  const dates = computeQuickRange(range);
  clearQuickDates();
  if (!active && range !== "all") { button.classList.add("quick-date--active"); button.setAttribute("aria-pressed", "true"); }
  state.startDate = dates.start; state.endDate = dates.end;
  els.startDate.value = dates.start; els.endDate.value = dates.end;
  fetchEvents();
}));

document.addEventListener("click", event => {
  const save = event.target.closest("[data-save-key]");
  if (save) {
    const key = save.dataset.saveKey;
    if (state.saved[key]) delete state.saved[key];
    else {
      const cards = [...document.querySelectorAll("[data-save-key]")];
      const source = cards.find(button => button.dataset.saveKey === key);
      const eventData = source?._event;
      if (eventData) state.saved[key] = eventData;
    }
    persistSaved(); fetchEvents(); renderSaved();
  }
  const performer = event.target.closest("[data-performer]");
  if (performer) {
    state.q = performer.dataset.performer; els.q.value = state.q;
    showView("events"); fetchEvents();
  }
});

persistSaved();
fetchEvents();
