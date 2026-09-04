const state = {
  q: "",
  location: "",
  startDate: "",
  endDate: "",
  sort: "date_asc",
};

const els = {
  grid: document.getElementById("event-grid"),
  count: document.getElementById("result-count"),
  status: document.getElementById("status-region"),
  q: document.getElementById("q-input"),
  location: document.getElementById("location-input"),
  startDate: document.getElementById("start-date"),
  endDate: document.getElementById("end-date"),
  sort: document.getElementById("sort-select"),
  chips: document.querySelectorAll(".chip"),
  quickDates: document.querySelectorAll(".quick-date"),
};

const ACCENTS = ["accent-a", "accent-b", "accent-c", "accent-d"];

let debounceTimer = null;
let requestToken = 0;

function scheduleFetch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fetchEvents, 300);
}

async function fetchEvents() {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.location) params.set("location", state.location);
  if (state.startDate) params.set("start_date", state.startDate);
  if (state.endDate) params.set("end_date", state.endDate);
  params.set("sort", state.sort);
  params.set("limit", "60");

  const token = ++requestToken;
  renderLoading();

  try {
    const response = await fetch(`/api/events?${params.toString()}`);
    if (token !== requestToken) return; // a newer request has since started

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${response.status})`);
    }

    const data = await response.json();
    if (token !== requestToken) return;
    renderEvents(data);
  } catch (error) {
    if (token !== requestToken) return;
    renderError(
      error instanceof TypeError
        ? "Couldn't reach the server. Check your connection and try again."
        : error.message || "Something went wrong."
    );
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

  if (data.count === 0) {
    els.status.hidden = false;
    els.status.className = "status status--empty";
    els.status.textContent = "No shows match your filters yet. Try widening the search.";
    els.grid.hidden = true;
    return;
  }

  els.status.hidden = true;
  els.grid.hidden = false;
  els.grid.innerHTML = data.events.map(renderCard).join("");
}

function renderCard(event, index) {
  const accent = ACCENTS[index % ACCENTS.length];
  const { day, month, weekdayLabel } = formatDateParts(event.date);
  const link = event.ticket_url || "#";

  const badges = [];
  if (event.sold_out) {
    badges.push('<span class="badge badge--sold-out">Sold out</span>');
  }
  if (typeof event.distance_miles === "number") {
    badges.push(`<span class="badge badge--distance">${event.distance_miles.toFixed(1)} mi away</span>`);
  }

  return `
    <article class="card">
      <div class="card__top">
        <div class="card__date ${accent}">
          <span class="card__month">${escapeHtml(month)}</span>
          <span class="card__day">${escapeHtml(day)}</span>
        </div>
        <span class="card__weekday">${escapeHtml(weekdayLabel)}</span>
      </div>
      <div class="card__badges">${badges.join("")}</div>
      <h3 class="card__performer">${escapeHtml(event.performer)}</h3>
      <p class="card__venue">${escapeHtml(event.venue || "Venue TBA")}</p>
      <p class="card__location">${escapeHtml(event.location || "Location TBA")}</p>
      <div class="card__footer">
        <a class="card__link" href="${escapeAttribute(link)}" target="_blank" rel="noopener noreferrer">
          ${event.sold_out ? "Details" : "Tickets"} ↗
        </a>
      </div>
    </article>
  `;
}

function formatDateParts(iso) {
  if (!iso) {
    return { day: "?", month: "TBD", weekdayLabel: "Date TBA" };
  }

  const parsed = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return { day: "?", month: "TBD", weekdayLabel: iso };
  }

  const day = parsed.toLocaleDateString(undefined, { day: "2-digit" });
  const month = parsed.toLocaleDateString(undefined, { month: "short" }).toUpperCase();
  const weekdayLabel = parsed.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return { day, month, weekdayLabel };
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function escapeAttribute(value) {
  return (value ?? "").replace(/"/g, "&quot;");
}

function computeQuickRange(range) {
  const today = new Date();
  const toISO = (d) => d.toISOString().slice(0, 10);

  if (range === "weekend") {
    const dayOfWeek = today.getDay();
    const daysUntilSaturday = (6 - dayOfWeek + 7) % 7;
    const saturday = new Date(today);
    saturday.setDate(today.getDate() + daysUntilSaturday);
    const sunday = new Date(saturday);
    sunday.setDate(saturday.getDate() + 1);
    return { start: toISO(today), end: toISO(sunday) };
  }

  if (range === "30days") {
    const end = new Date(today);
    end.setDate(today.getDate() + 30);
    return { start: toISO(today), end: toISO(end) };
  }

  return { start: "", end: "" };
}

function clearQuickDateSelection() {
  els.quickDates.forEach((button) => {
    button.classList.remove("quick-date--active");
    button.setAttribute("aria-pressed", "false");
  });
}

// --- wire up controls -------------------------------------------------

els.q.addEventListener("input", (event) => {
  state.q = event.target.value.trim();
  scheduleFetch();
});

els.location.addEventListener("input", (event) => {
  state.location = event.target.value.trim();
  els.chips.forEach((chip) => {
    const isActive = chip.dataset.location === state.location;
    chip.classList.toggle("chip--active", isActive);
    chip.setAttribute("aria-pressed", String(isActive));
  });
  if (![...els.chips].some((chip) => chip.dataset.location === state.location)) {
    els.chips.forEach((chip) => chip.classList.remove("chip--active"));
  }
  scheduleFetch();
});

els.startDate.addEventListener("change", (event) => {
  state.startDate = event.target.value;
  clearQuickDateSelection();
  fetchEvents();
});

els.endDate.addEventListener("change", (event) => {
  state.endDate = event.target.value;
  clearQuickDateSelection();
  fetchEvents();
});

els.sort.addEventListener("change", (event) => {
  state.sort = event.target.value;
  fetchEvents();
});

els.chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const isActive = chip.classList.contains("chip--active");
    els.chips.forEach((candidate) => {
      candidate.classList.remove("chip--active");
      candidate.setAttribute("aria-pressed", "false");
    });
    if (!isActive) {
      chip.classList.add("chip--active");
      chip.setAttribute("aria-pressed", "true");
    }
    state.location = isActive ? "" : chip.dataset.location || "";
    els.location.value = state.location;
    fetchEvents();
  });
});

els.quickDates.forEach((button) => {
  button.addEventListener("click", () => {
    const isActive = button.classList.contains("quick-date--active");
    const range = isActive ? "all" : button.dataset.range;
    const { start, end } = computeQuickRange(range);
    clearQuickDateSelection();
    if (!isActive && range !== "all") {
      button.classList.add("quick-date--active");
      button.setAttribute("aria-pressed", "true");
    }
    state.startDate = start;
    state.endDate = end;
    els.startDate.value = start;
    els.endDate.value = end;
    fetchEvents();
  });
});

fetchEvents();
