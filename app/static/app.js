/* Moímetro: interface uses textContent for patient data, never raw HTML. */
"use strict";

const el = id => document.getElementById(id);
const setupToken = (() => {
  const fragment = window.location.hash || "";
  if (!fragment.startsWith("#setup=")) return null;
  const token = decodeURIComponent(fragment.slice(7));
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return token;
})();

function setupVisibility(required) {
  el("setupPanel").hidden = !required;
  el("loginForm").hidden = required;
  el("loginHeading").textContent = required ? "Configurar Moímetro" : "Iniciar sesión";
}

async function checkFirstRun() {
  const status = await api("/api/setup/status");
  setupVisibility(Boolean(status.required && status.available && setupToken));
  if (status.required && !status.available) {
    toast("Configure el administrador desde el comando de instalación.", true);
  }
}

const state = { token: null, role: "", username: "", patient: null,
                encounter: null, capture: null };

// List state stays bounded regardless of the number of records in SQLite.
const directory = { cursor: null, previous: [], page: 1, next: null, request: 0 };
const visits = { cursor: null, previous: [], page: 1, next: null, request: 0 };
const staffPaging = { cursor: null, previous: [], page: 1, next: null, request: 0 };
const revisionPaging = { cursor: null, previous: [], page: 1, next: null, request: 0 };
let managedStaff = null;
let selectedPatientVersion = 0;
const DIRECTORY_LIMIT = 25;
const VISIT_LIMIT = 15;

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
  if (!Object.prototype.hasOwnProperty.call(views, view)) return;
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

function showScreen(area) {
  const screens = {
    directory: "directoryScreen",
    registration: "registrationScreen",
    patient: "patientScreen",
    staff: "adminSection"
  };
  if (!Object.prototype.hasOwnProperty.call(screens, area)) return;
  for (const [name, id] of Object.entries(screens)) {
    el(id).hidden = name !== area;
  }
  const active = area === "staff" ? "navStaff" : "navPatients";
  for (const id of ["navPatients", "navStaff"]) {
    const node = el(id);
    node.classList.toggle("selected", id === active);
    if (id === active) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  }
}

function showLogin() {
  ++directory.request;
  ++visits.request;
  ++staffPaging.request;
  ++revisionPaging.request;
  managedStaff = null;
  el("accountPanel").hidden = true;
  el("staffManagePanel").hidden = true;
  el("passwordForm").reset();
  el("changePasswordButton").hidden = true;
  ++selectedPatientVersion;
  el("loginScreen").hidden = false;
  el("workScreen").hidden = true;
  el("logoutButton").hidden = true;
  el("identity").textContent = "";
  state.patient = null;
  state.encounter = null;
  state.capture = null;
  state.role = "";
  el("patientWork").hidden = true;
  showScreen("directory");
}

function showWork() {
  el("loginScreen").hidden = true;
  el("workScreen").hidden = false;
  el("logoutButton").hidden = false;
  el("changePasswordButton").hidden = false;
  el("navStaff").hidden = state.role !== "admin";
  const roles = { admin: "Administración", reception: "Recepción",
                  nurse: "Enfermería", clinician: "Medicina" };
  el("identity").textContent = state.username + " · " + (roles[state.role] || state.role);
  showScreen("directory");
}

function resetDirectoryPages() {
  directory.cursor = null;
  directory.previous = [];
  directory.page = 1;
  directory.next = null;
}

function resetVisitPages() {
  visits.cursor = null;
  visits.previous = [];
  visits.page = 1;
  visits.next = null;
  ++visits.request;
}

function addCell(row, value) {
  const td = document.createElement("td");
  td.textContent = value == null || value === "" ? "—" : String(value);
  row.appendChild(td);
  return td;
}

async function loadPatients() {
  const request = ++directory.request;
  const q = el("search").value.trim();
  const type = el("directoryDocumentType").value;
  const query = new URLSearchParams({ limit: String(DIRECTORY_LIMIT) });
  if (q) query.set("q", q);
  if (type) query.set("document_type", type);
  if (directory.cursor) query.set("before", String(directory.cursor));
  el("directoryStatus").textContent = "Buscando pacientes…";
  const result = await api("/api/patients/directory?" + query.toString());
  if (request !== directory.request || !state.token) return;
  directory.next = result.next_cursor;
  const list = el("patientList");
  clearChildren(list);
  if (!result.items.length) {
    const tr = document.createElement("tr");
    const td = addCell(tr, q || type ? "No se encontraron pacientes. Cambia la búsqueda o los filtros." :
      "Todavía no hay pacientes registrados.");
    td.colSpan = 6;
    td.className = "empty-table-cell";
    list.appendChild(tr);
  }
  for (const patient of result.items) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "table-patient-link";
    open.textContent = patient.full_name;
    open.addEventListener("click", () => selectPatient(patient.id).catch(error => toast(error.message, true)));
    name.appendChild(open);
    tr.appendChild(name);
    addCell(tr, patient.document_type + "-" + patient.document_number);
    addCell(tr, patient.birth_date);
    addCell(tr, patient.phone);
    addCell(tr, patient.visits);
    const action = document.createElement("td");
    const view = document.createElement("button");
    view.type = "button";
    view.className = "button button-table";
    view.textContent = "Abrir";
    view.setAttribute("aria-label", "Abrir expediente de " + patient.full_name);
    view.addEventListener("click", () => selectPatient(patient.id).catch(error => toast(error.message, true)));
    action.appendChild(view);
    tr.appendChild(action);
    list.appendChild(tr);
  }
  const count = result.items.length;
  el("directoryStatus").textContent =
    count + (count === 1 ? " registro en esta página" : " registros en esta página")
    + (q ? " · Búsqueda: " + q : "")
    + (type ? " · Documento: " + type : "");
  el("directoryPageLabel").textContent = "Página " + directory.page;
  el("directoryPrev").disabled = directory.previous.length === 0;
  el("directoryNext").disabled = !directory.next;
}

function resetStaffPages() {
  staffPaging.cursor = null;
  staffPaging.previous = [];
  staffPaging.page = 1;
  staffPaging.next = null;
}

async function loadStaff() {
  if (state.role !== "admin") return;
  const request = ++staffPaging.request;
  const q = el("staffSearch").value.trim();
  const query = new URLSearchParams({ limit: "20" });
  if (q) query.set("q", q);
  if (staffPaging.cursor) query.set("before", String(staffPaging.cursor));
  el("staffStatus").textContent = "Cargando personal…";
  const result = await api("/api/admin/users?" + query.toString());
  if (request !== staffPaging.request || !state.token) return;
  staffPaging.next = result.next_cursor;
  const tbody = el("staffList");
  clearChildren(tbody);
  const roles = { admin: "Administración", reception: "Recepción",
                  nurse: "Enfermería", clinician: "Medicina" };
  for (const person of result.items) {
    const tr = document.createElement("tr");
    addCell(tr, person.username);
    addCell(tr, roles[person.role] || person.role);
    addCell(tr, person.active ? "Activo" : "Desactivado");
    addCell(tr, dateText(person.created_at));
    const action = document.createElement("td");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "button button-table";
    open.textContent = "Administrar";
    open.setAttribute("aria-label", "Administrar usuario " + person.username);
    open.addEventListener("click", () => {
      managedStaff = person;
      el("staffManageTitle").textContent = "Administrar · " + person.username;
      el("staffManageForm").elements.role.value = person.role;
      el("staffManageForm").elements.active.value = String(Boolean(person.active));
      el("staffManageForm").elements.password.value = "";
      const self = person.username === state.username;
      el("staffManageForm").elements.role.disabled = self;
      el("staffManageForm").elements.active.disabled = self;
      el("staffCreatePanel").hidden = true;
      el("staffManagePanel").hidden = false;
      el("staffManagePanel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    action.appendChild(open);
    tr.appendChild(action);
    tbody.appendChild(tr);
  }
  if (!result.items.length) {
    const tr = document.createElement("tr");
    const td = addCell(tr, "No hay usuarios en esta página.");
    td.colSpan = 5;
    td.className = "empty-table-cell";
    tbody.appendChild(tr);
  }
  const count = result.items.length;
  el("staffStatus").textContent =
    count + (count === 1 ? " usuario" : " usuarios") + " en esta página";
  el("staffPageLabel").textContent = "Página " + staffPaging.page;
  el("staffPrev").disabled = staffPaging.previous.length === 0;
  el("staffNext").disabled = !staffPaging.next;
}

async function loadRevisions() {
  if (!state.patient || !mayClinicallyEdit()) return;
  const request = ++revisionPaging.request;
  const patientId = state.patient.id;
  const query = new URLSearchParams({ limit: "15" });
  if (revisionPaging.cursor) query.set("before", String(revisionPaging.cursor));
  const data = await api("/api/patients/" + patientId + "/revisions?" + query.toString());
  if (request !== revisionPaging.request || patientId !== state.patient?.id || !state.token) return;
  revisionPaging.next = data.next_cursor;
  const list = el("revisionList");
  clearChildren(list);
  const labels = {
    patient: "Datos personales", history: "Antecedentes", encounter: "Consulta"
  };
  if (!data.items.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No se registran cambios en esta página.";
    list.appendChild(empty);
  }
  for (const entry of data.items) {
    const item = document.createElement("article");
    item.className = "revision-item";
    const title = document.createElement("strong");
    title.textContent = (labels[entry.resource] || "Registro") +
      (entry.encounter_id ? " #" + entry.encounter_id : "");
    const detail = document.createElement("p");
    detail.textContent = dateText(entry.created_at) + " · " + entry.actor +
      " · " + entry.reason;
    const fields = document.createElement("small");
    fields.textContent = "Campos modificados: " + (entry.fields.join(", ") || "—");
    item.appendChild(title);
    item.appendChild(detail);
    item.appendChild(fields);
    list.appendChild(item);
  }
  el("revisionPageLabel").textContent = "Página " + revisionPaging.page;
  el("revisionPrev").disabled = revisionPaging.previous.length === 0;
  el("revisionNext").disabled = !revisionPaging.next;
}

async function selectPatient(id) {
  const version = ++selectedPatientVersion;
  const selected = await api("/api/patients/" + id);
  const history = await api("/api/patients/" + id + "/history");
  if (version !== selectedPatientVersion || !state.token) return;
  state.patient = selected;
  state.encounter = null;
  state.capture = null;
  resetVisitPages();
  revisionPaging.cursor = null;
  revisionPaging.previous = [];
  revisionPaging.page = 1;
  revisionPaging.next = null;
  ++revisionPaging.request;
  el("revisionPanel").hidden = !mayClinicallyEdit();
  el("patientTitle").textContent = selected.full_name;
  el("patientDetails").textContent =
    "Documento " + selected.document_type + "-" + selected.document_number +
    (selected.birth_date ? " · Nacimiento: " + selected.birth_date : "");
  el("patientEditForm").elements.full_name.value = selected.full_name;
  el("patientEditForm").elements.birth_date.value = selected.birth_date || "";
  el("patientEditForm").elements.phone.value = selected.phone || "";
  el("historyForm").elements.allergies.value = history.allergies;
  el("historyForm").elements.background.value = history.background;
  for (const control of el("historyForm").querySelectorAll("textarea,button")) {
    control.disabled = !mayClinicallyEdit();
  }
  el("patientWork").hidden = false;
  el("encounterWork").hidden = true;
  el("encounterEmpty").hidden = false;
  setActiveView("overview");
  showScreen("patient");
  await loadEncounters();
}

async function loadEncounters() {
  if (!state.patient) return;
  const patientId = state.patient.id;
  const request = ++visits.request;
  const query = new URLSearchParams({ patient_id: String(patientId),
    limit: String(VISIT_LIMIT) });
  if (visits.cursor) query.set("before", String(visits.cursor));
  const result = await api("/api/encounters/directory?" + query.toString());
  if (request !== visits.request || patientId !== state.patient?.id || !state.token) return;
  visits.next = result.next_cursor;
  const list = el("encounterList");
  clearChildren(list);
  if (!result.items.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No hay consultas en esta página.";
    list.appendChild(p);
  }
  for (const visit of result.items) {
    list.appendChild(button("Consulta #" + visit.id + " · " +
      (visit.status === "open" ? "Abierta" : "Cerrada"),
      dateText(visit.opened_at) + " · " + visit.reason,
      () => selectEncounter(visit.id), state.encounter?.id === visit.id));
  }
  el("visitPageLabel").textContent = "Página " + visits.page;
  el("visitListPrev").disabled = visits.previous.length === 0;
  el("visitListNext").disabled = !visits.next;
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
  tab.addEventListener("click", safe(async () => {
    setActiveView(tab.dataset.view);
    if (tab.dataset.view === "profile") await loadRevisions();
  }));
}
el("backToVisitsButton").addEventListener("click", () => setActiveView("overview"));

el("setupForm").addEventListener("submit", safe(async event => {
  if (!setupToken) throw new Error("Abra el programa desde el acceso directo.");
  const form = formValue(event.target);
  if (form.password !== form.confirm) {
    throw new Error("Las contraseñas no coinciden.");
  }
  await api("/api/setup/admin", {
    method: "POST",
    headers: { "X-Setup-Token": setupToken },
    body: JSON.stringify({ username: form.username, password: form.password })
  });
  event.target.reset();
  setupVisibility(false);
  toast("Administrador creado. Inicie sesión.");
}));
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
el("navPatients").addEventListener("click", safe(async () => {
  showScreen("directory");
  await loadPatients();
}));
el("navStaff").addEventListener("click", safe(async () => {
  if (state.role !== "admin") return;
  showScreen("staff");
  el("staffManagePanel").hidden = true;
  managedStaff = null;
  await loadStaff();
}));
el("newStaffButton").addEventListener("click", () => {
  el("staffManagePanel").hidden = true;
  managedStaff = null;
  el("staffCreatePanel").hidden = !el("staffCreatePanel").hidden;
});
el("cancelStaffButton").addEventListener("click", () => {
  el("staffCreatePanel").hidden = true;
  el("staffForm").reset();
});
let staffSearchTimer = null;
el("staffSearch").addEventListener("input", () => {
  clearTimeout(staffSearchTimer);
  staffSearchTimer = setTimeout(() => {
    resetStaffPages();
    loadStaff().catch(error => toast(error.message, true));
  }, 350);
});
el("staffNext").addEventListener("click", safe(async () => {
  if (!staffPaging.next) return;
  staffPaging.previous.push(staffPaging.cursor);
  staffPaging.cursor = staffPaging.next;
  staffPaging.page++;
  await loadStaff();
}));
el("staffPrev").addEventListener("click", safe(async () => {
  if (!staffPaging.previous.length) return;
  staffPaging.cursor = staffPaging.previous.pop();
  staffPaging.page--;
  await loadStaff();
}));
el("cancelStaffManage").addEventListener("click", () => {
  managedStaff = null;
  el("staffManagePanel").hidden = true;
  el("staffManageForm").reset();
});
el("staffManageForm").addEventListener("submit", safe(async event => {
  if (!managedStaff) return;
  const form = formValue(event.target);
  const payload = {
    role: form.role,
    active: form.active === "true"
  };
  if (form.password) payload.password = form.password;
  if (managedStaff.username === state.username && form.password) {
    throw new Error("Cambie su propia contraseña desde «Mi contraseña».");
  }
  if (!payload.active && !confirm("¿Bloquear el acceso de este usuario?")) return;
  await api("/api/admin/users/" + managedStaff.id, {
    method: "PATCH", body: JSON.stringify(payload)
  });
  el("staffManagePanel").hidden = true;
  managedStaff = null;
  resetStaffPages();
  await loadStaff();
  toast("Permisos y sesiones actualizados.");
}));
el("changePasswordButton").addEventListener("click", () => {
  el("accountPanel").hidden = false;
  el("passwordForm").elements.current_password.focus();
});
el("closeAccountPanel").addEventListener("click", () => {
  el("accountPanel").hidden = true;
  el("passwordForm").reset();
});
el("passwordForm").addEventListener("submit", safe(async event => {
  const values = formValue(event.target);
  if (values.new_password !== values.confirmation) {
    throw new Error("Las contraseñas no coinciden.");
  }
  await api("/api/auth/change-password", {
    method: "POST", body: JSON.stringify({
      current_password: values.current_password,
      new_password: values.new_password
    })
  });
  state.token = null;
  showLogin();
  toast("Contraseña actualizada. Inicie sesión de nuevo.");
}));
el("revisionNext").addEventListener("click", safe(async () => {
  if (!revisionPaging.next) return;
  revisionPaging.previous.push(revisionPaging.cursor);
  revisionPaging.cursor = revisionPaging.next;
  revisionPaging.page++;
  await loadRevisions();
}));
el("revisionPrev").addEventListener("click", safe(async () => {
  if (!revisionPaging.previous.length) return;
  revisionPaging.cursor = revisionPaging.previous.pop();
  revisionPaging.page--;
  await loadRevisions();
}));
el("newPatientButton").addEventListener("click", () => showScreen("registration"));
el("cancelPatientButton").addEventListener("click", safe(async () => {
  showScreen("directory");
  await loadPatients();
}));
el("backToDirectory").addEventListener("click", safe(async () => {
  showScreen("directory");
  await loadPatients();
}));
el("searchButton").addEventListener("click", safe(async () => {
  resetDirectoryPages();
  await loadPatients();
}));
let searchTimer = null;
el("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    resetDirectoryPages();
    loadPatients().catch(error => toast(error.message, true));
  }, 350);
});
el("search").addEventListener("keydown", event => {
  if (event.key === "Enter") {
    event.preventDefault();
    clearTimeout(searchTimer);
    resetDirectoryPages();
    loadPatients().catch(error => toast(error.message, true));
  }
});
el("directoryDocumentType").addEventListener("change", safe(async () => {
  resetDirectoryPages();
  await loadPatients();
}));
el("directoryNext").addEventListener("click", safe(async () => {
  if (!directory.next) return;
  directory.previous.push(directory.cursor);
  directory.cursor = directory.next;
  directory.page++;
  await loadPatients();
}));
el("directoryPrev").addEventListener("click", safe(async () => {
  if (!directory.previous.length) return;
  directory.cursor = directory.previous.pop();
  directory.page--;
  await loadPatients();
}));
el("visitListNext").addEventListener("click", safe(async () => {
  if (!visits.next || !state.patient) return;
  visits.previous.push(visits.cursor);
  visits.cursor = visits.next;
  visits.page++;
  await loadEncounters();
}));
el("visitListPrev").addEventListener("click", safe(async () => {
  if (!visits.previous.length || !state.patient) return;
  visits.cursor = visits.previous.pop();
  visits.page--;
  await loadEncounters();
}));
el("patientForm").addEventListener("submit", safe(async e => {
  const form = formValue(e.target);
  const created = await api("/api/patients", {
    method: "POST",
    body: JSON.stringify({ ...form, birth_date: form.birth_date || null, phone: form.phone || null })
  });
  e.target.reset();
  toast("Paciente registrado.");
  await selectPatient(created.id);
}));
el("patientEditForm").addEventListener("submit", safe(async e => {
  if (!state.patient) return;
  const form = formValue(e.target);
  await api("/api/patients/" + state.patient.id, {
    method: "PATCH", body: JSON.stringify({
      ...form, birth_date: form.birth_date || null, phone: form.phone || null,
      reason: form.reason || null
    })
  });
  await selectPatient(state.patient.id);
  el("patientEditForm").elements.reason.value = "";
  setActiveView("profile");
  await loadRevisions();
  toast("Datos personales actualizados.");
}));
el("historyForm").addEventListener("submit", safe(async e => {
  if (!state.patient) return;
  await api("/api/patients/" + state.patient.id + "/history", {
    method: "PUT", body: JSON.stringify({
      ...formValue(e.target),
      reason: e.target.elements.reason.value || null
    })
  });
  e.target.elements.reason.value = "";
  await loadRevisions();
  toast("Antecedentes actualizados.");
}));
el("staffForm").addEventListener("submit", safe(async e => {
  await api("/api/admin/users", { method: "POST", body: JSON.stringify(formValue(e.target)) });
  e.target.reset();
  el("staffCreatePanel").hidden = true;
  resetStaffPages();
  await loadStaff();
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
    method: "PATCH", body: JSON.stringify({
      ...values, reason: values.reason || null
    })
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
checkFirstRun().catch(error => toast(error.message, true));
