/* Moímetro: interface uses textContent for patient data, never raw HTML. */
"use strict";

const el = id => document.getElementById(id);
const state = { token: null, role: "", username: "", patient: null,
                encounter: null, capture: null };
const mayMeasure = () => ["admin", "nurse", "clinician"].includes(state.role);
const mayClinicallyEdit = () => ["admin", "clinician"].includes(state.role);
const labels = {
  body_temp_c: "Temperatura corporal", pulse_bpm: "Frecuencia cardíaca",
  spo2_pct: "SpO₂ (manual)", ambient_temp_c: "Temperatura ambiente",
  humidity_pct: "Humedad ambiental"
};

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const response = await fetch(path, { ...options, headers, cache: "no-store" });
  let data = null;
  try { data = await response.json(); } catch { /* no body */ }
  if (!response.ok) {
    const message = typeof data?.detail === "string" ? data.detail :
      Array.isArray(data?.detail) ? data.detail.map(e => e.msg).join("; ") :
      "No se pudo completar la operación.";
    if (response.status === 401 && state.token) {
      state.token = null;
      showLogin();
    }
    throw new Error(message);
  }
  return data;
}

let toastTimer = null;
function toast(message, isError = false) {
  const node = el("toast");
  node.textContent = message;
  node.className = "show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.className = ""; }, 4500);
}
const dateText = stamp => stamp ? new Date(stamp).toLocaleString("es-VE") : "—";
function clearChildren(node) { node.replaceChildren(); }
function button(label, sub, action, selected = false) {
  const node = document.createElement("button");
  node.type = "button";
  node.className = "list-button" + (selected ? " selected" : "");
  const strong = document.createElement("strong");
  strong.textContent = label;
  node.appendChild(strong);
  if (sub) {
    const small = document.createElement("small");
    small.textContent = sub;
    node.appendChild(small);
  }
  node.addEventListener("click", () => action().catch(error => toast(error.message, true)));
  return node;
}
function setActiveView(view) {
  const views = {
    overview: "viewOverview",
    profile: "viewProfile",
    consultation: "viewEncounter"
  };
  if (!Object.hasOwn(views, view)) return;
  for (const [name, id] of Object.entries(views)) {
    el(id).hidden = name !== view;
  }
  for (const tab of document.querySelectorAll(".tab-button")) {
    const active = tab.dataset.view === view;
    tab.classList.toggle("active", active);
    if (active) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
}

function showLogin() {
  el("loginScreen").hidden = false;
  el("workScreen").hidden = true;
  el("logoutButton").hidden = true;
  el("identity").textContent = "";
  state.patient = null;
  state.encounter = null;
  state.capture = null;
  el("patientWork").hidden = true;
  el("emptyState").hidden = false;
  el("patientTitle").textContent = "Pacientes";
  el("patientDetails").textContent = "Selecciona un paciente para comenzar.";
}
function showWork() {
  el("loginScreen").hidden = true;
  el("workScreen").hidden = false;
  el("logoutButton").hidden = false;
  el("adminSection").hidden = state.role !== "admin";
  const roles = { admin: "Administración", reception: "Recepción",
                  nurse: "Enfermería", clinician: "Medicina" };
  el("identity").textContent = state.username + " · " + (roles[state.role] || state.role);
  el("emptyState").hidden = Boolean(state.patient);
}

async function loadPatients() {
  const q = el("search").value.trim();
  const patients = await api("/api/patients?q=" + encodeURIComponent(q));
  const list = el("patientList");
  clearChildren(list);
  if (!patients.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No hay pacientes para esta búsqueda.";
    list.appendChild(p);
  }
  for (const patient of patients) {
    list.appendChild(button(patient.full_name,
      patient.document_type + "-" + patient.document_number,
      () => selectPatient(patient.id), state.patient?.id === patient.id));
  }
}

async function selectPatient(id) {
  state.patient = await api("/api/patients/" + id);
  state.encounter = null;
  state.capture = null;
  el("patientTitle").textContent = state.patient.full_name;
  el("patientDetails").textContent =
    "Documento " + state.patient.document_type + "-" + state.patient.document_number +
    (state.patient.birth_date ? " · Nacimiento: " + state.patient.birth_date : "");
  el("patientEditForm").elements.full_name.value = state.patient.full_name;
  el("patientEditForm").elements.birth_date.value = state.patient.birth_date || "";
  el("patientEditForm").elements.phone.value = state.patient.phone || "";
  const history = await api("/api/patients/" + id + "/history");
  el("historyForm").elements.allergies.value = history.allergies;
  el("historyForm").elements.background.value = history.background;
  for (const control of el("historyForm").querySelectorAll("textarea,button")) {
    control.disabled = !mayClinicallyEdit();
  }
  el("patientWork").hidden = false;
  el("emptyState").hidden = true;
  el("encounterWork").hidden = true;
  el("encounterEmpty").hidden = false;
  setActiveView("overview");
  await Promise.all([loadEncounters(), loadPatients()]);
}

async function loadEncounters() {
  if (!state.patient) return;
  const visits = await api("/api/encounters?patient_id=" + state.patient.id);
  const list = el("encounterList");
  clearChildren(list);
  if (!visits.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No hay consultas anteriores.";
    list.appendChild(p);
  }
  for (const visit of visits) {
    list.appendChild(button("Consulta #" + visit.id + " · " +
      (visit.status === "open" ? "Abierta" : "Cerrada"),
      dateText(visit.opened_at) + " · " + visit.reason,
      () => selectEncounter(visit.id), state.encounter?.id === visit.id));
  }
}

async function selectEncounter(id) {
  const encounter = await api("/api/encounters/" + id);
  if (encounter.patient_id !== state.patient?.id)
    throw new Error("La consulta no pertenece al paciente seleccionado.");
  state.encounter = encounter;
  el("encounterEmpty").hidden = true;
  el("encounterWork").hidden = false;
  setActiveView("consultation");
  el("encounterMeta").textContent = "#" + encounter.id + " · " +
    dateText(encounter.opened_at) + " · " + (encounter.status === "open" ? "Abierta" : "Cerrada");
  const open = encounter.status === "open";
  el("clinicalForm").elements.assessment.value = encounter.assessment;
  el("clinicalForm").elements.diagnosis.value = encounter.diagnosis;
  el("clinicalForm").elements.treatment.value = encounter.treatment;
  for (const field of el("clinicalForm").querySelectorAll("textarea,button")) {
    field.disabled = !open || !mayClinicallyEdit();
  }
  for (const control of el("manualForm").querySelectorAll("input,select,textarea,button")) {
    control.disabled = !open || !mayMeasure();
  }
  el("closeEncounterButton").disabled = !open || !mayClinicallyEdit();
  await Promise.all([refreshCapture(), refreshReadings(), loadEncounters()]);
}

async function refreshCapture() {
  if (!state.encounter) return;
  state.capture = await api("/api/encounters/" + state.encounter.id + "/capture");
  const active = state.capture && !state.capture.ended_at;
  el("captureState").textContent = active
    ? "Captura activa · dispositivo " + state.capture.device_id
    : "Sin sesión activa";
  const allowed = state.encounter.status === "open" && mayMeasure();
  el("startCaptureButton").disabled = !allowed || Boolean(active);
  el("stopCaptureButton").disabled = !allowed || !active;
}

async function refreshReadings() {
  if (!state.encounter) return;
  const readings = await api("/api/measurements?encounter_id=" + state.encounter.id);
  const target = el("measurementList");
  clearChildren(target);
  if (!readings.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.textContent = "No hay mediciones registradas.";
    tr.appendChild(td);
    target.appendChild(tr);
  }
  for (const m of readings) {
    const row = document.createElement("tr");
    const fields = [
      dateText(m.received_at), labels[m.kind] || m.kind,
      m.value === null ? "No disponible" : String(m.value) + " " + m.unit,
      m.origin === "manual" ? "Manual" : "ESP32",
      m.status === "accepted" ? "Aceptada" :
        m.status === "rejected" ? "Descartada" : "Pendiente"
    ];
    for (const item of fields) {
      const td = document.createElement("td");
      td.textContent = item;
      row.appendChild(td);
    }
    row.children[4].className = "badge " + m.status;
    const action = document.createElement("td");
    if (m.status === "pending" && mayMeasure() && state.encounter.status === "open") {
      const accept = document.createElement("button");
      accept.type = "button";
      accept.textContent = "Aceptar";
      accept.addEventListener("click", () => actOnReading(m.id, "accept"));
      const reject = document.createElement("button");
      reject.type = "button";
      reject.textContent = "Rechazar";
      reject.addEventListener("click", () => actOnReading(m.id, "reject"));
      action.append(accept, reject);
    } else if (m.quality !== "ok") {
      action.textContent = m.quality;
    } else {
      action.textContent = "—";
    }
    row.appendChild(action);
    target.appendChild(row);
  }
}

async function actOnReading(id, action) {
  try {
    await api("/api/measurements/" + id + "/" + action, { method: "POST" });
    toast(action === "accept" ? "Lectura aceptada." : "Lectura rechazada.");
    await refreshReadings();
  } catch (error) {
    toast(error.message, true);
  }
}

function formValue(form) { return Object.fromEntries(new FormData(form).entries()); }
function safe(fn) {
  return async event => {
    event?.preventDefault();
    try { await fn(event); } catch (error) { toast(error.message, true); }
  };
}

for (const tab of document.querySelectorAll(".tab-button")) {
  tab.addEventListener("click", () => setActiveView(tab.dataset.view));
}
el("backToVisitsButton").addEventListener("click", () => setActiveView("overview"));

el("loginForm").addEventListener("submit", safe(async event => {
  const values = formValue(event.target);
  const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(values) });
  state.token = data.token;
  state.username = data.username;
  state.role = data.role;
  event.target.reset();
  showWork();
  await loadPatients();
}));
el("logoutButton").addEventListener("click", safe(async () => {
  try { await api("/api/auth/logout", { method: "POST" }); }
  finally { state.token = null; showLogin(); }
}));
el("searchButton").addEventListener("click", safe(loadPatients));
el("search").addEventListener("keydown", e => {
  if (e.key === "Enter") { e.preventDefault(); loadPatients().catch(error => toast(error.message, true)); }
});
el("patientForm").addEventListener("submit", safe(async e => {
  const form = formValue(e.target);
  const created = await api("/api/patients", {
    method: "POST",
    body: JSON.stringify({ ...form, birth_date: form.birth_date || null, phone: form.phone || null })
  });
  e.target.reset();
  toast("Paciente registrado.");
  await selectPatient(created.id);
  el("newPatientDetails").open = false;
}));
el("patientEditForm").addEventListener("submit", safe(async e => {
  if (!state.patient) return;
  const form = formValue(e.target);
  await api("/api/patients/" + state.patient.id, {
    method: "PATCH", body: JSON.stringify({
      ...form, birth_date: form.birth_date || null, phone: form.phone || null
    })
  });
  await selectPatient(state.patient.id);
  setActiveView("profile");
  toast("Datos personales actualizados.");
}));
el("historyForm").addEventListener("submit", safe(async e => {
  if (!state.patient) return;
  await api("/api/patients/" + state.patient.id + "/history", {
    method: "PUT", body: JSON.stringify(formValue(e.target))
  });
  toast("Antecedentes actualizados.");
}));
el("staffForm").addEventListener("submit", safe(async e => {
  await api("/api/admin/users", { method: "POST", body: JSON.stringify(formValue(e.target)) });
  e.target.reset();
  toast("Cuenta de personal creada.");
}));
el("encounterForm").addEventListener("submit", safe(async e => {
  if (!state.patient) return;
  const { reason } = formValue(e.target);
  const visit = await api("/api/encounters", {
    method: "POST", body: JSON.stringify({ patient_id: state.patient.id, reason })
  });
  e.target.reset();
  await selectEncounter(visit.id);
  toast("Consulta creada.");
}));
el("clinicalForm").addEventListener("submit", safe(async e => {
  if (!state.encounter) return;
  const values = formValue(e.target);
  await api("/api/encounters/" + state.encounter.id, {
    method: "PATCH", body: JSON.stringify(values)
  });
  toast("Evolución clínica guardada.");
  await selectEncounter(state.encounter.id);
}));
el("startCaptureButton").addEventListener("click", safe(async () => {
  const capture = await api("/api/encounters/" + state.encounter.id + "/capture",
    { method: "POST" });
  toast("Captura iniciada: " + capture.device_id);
  await refreshCapture();
}));
el("stopCaptureButton").addEventListener("click", safe(async () => {
  if (!state.capture || state.capture.ended_at) return;
  await api("/api/capture/" + encodeURIComponent(state.capture.id) + "/stop",
    { method: "POST" });
  await refreshCapture();
  toast("Captura finalizada.");
}));
el("refreshReadingsButton").addEventListener("click", safe(async () => {
  await Promise.all([refreshCapture(), refreshReadings()]);
  toast("Lecturas actualizadas.");
}));
el("manualForm").addEventListener("submit", safe(async e => {
  const values = formValue(e.target);
  await api("/api/encounters/" + state.encounter.id + "/manual-measurements", {
    method: "POST", body: JSON.stringify({
      kind: values.kind, value: Number(values.value), notes: values.notes
    })
  });
  e.target.reset();
  await refreshReadings();
  toast("Medición manual registrada con origen identificado.");
}));
el("closeEncounterButton").addEventListener("click", safe(async () => {
  if (!state.encounter || !window.confirm("¿Cerrar definitivamente esta consulta?")) return;
  await api("/api/encounters/" + state.encounter.id + "/close", { method: "POST" });
  await selectEncounter(state.encounter.id);
  toast("Consulta cerrada.");
}));

window.setInterval(() => {
  if (state.token && state.encounter && state.capture && !state.capture.ended_at)
    Promise.all([refreshCapture(), refreshReadings()]).catch(error => toast(error.message, true));
}, 5000);
showLogin();
