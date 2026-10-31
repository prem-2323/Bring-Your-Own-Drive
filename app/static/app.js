const $ = (selector) => document.querySelector(selector);
let activeCollection = null;
let editingDocumentId = null;
let modalInstance;

document.addEventListener("DOMContentLoaded", () => {
  const modalEl = $("#documentModal");
  if (modalEl) modalInstance = new bootstrap.Modal(modalEl);
  $("#loadBtn")?.addEventListener("click", loadCollections);
  $("#createCollectionBtn")?.addEventListener("click", createCollection);
  $("#collectionName")?.addEventListener("keydown", (e) => { if (e.key === "Enter") createCollection(); });
  $("#newDocumentBtn")?.addEventListener("click", () => openDocumentEditor());
  $("#saveDocumentBtn")?.addEventListener("click", saveDocument);
  $("#logoutBtn")?.addEventListener("click", logout);
  if ($("#workspace") && !$("#workspace").classList.contains("d-none")) loadCollections();
  const params = new URLSearchParams(location.search);
  if (params.has("auth_config")) showAlert("Add Google OAuth credentials to your .env file before signing in.", "warning");
  if (params.has("auth_error")) showAlert("Google sign-in failed. Check OAuth settings and try again.", "danger");
});

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    if (response.status === 401) showAlert("Your session expired. Please sign in again.", "warning");
    throw new Error(payload?.detail || payload || `Request failed (${response.status})`);
  }
  return payload;
}

function showAlert(message, type = "danger") {
  const area = $("#alertArea");
  if (!area) return;
  area.innerHTML = "";
  const alert = document.createElement("div");
  alert.className = `alert alert-${type} alert-dismissible fade show`;
  alert.setAttribute("role", "alert");
  alert.textContent = message;
  const close = document.createElement("button");
  close.type = "button"; close.className = "btn-close"; close.setAttribute("data-bs-dismiss", "alert");
  close.setAttribute("aria-label", "Close");
  alert.appendChild(close); area.appendChild(alert);
}
function clearAlert() { if ($("#alertArea")) $("#alertArea").innerHTML = ""; }

async function loadCollections() {
  clearAlert();
  const container = $("#collections");
  if (!container) return;
  container.innerHTML = '<div class="col-12"><div class="feature-card text-secondary">Loading your Drive collections…</div></div>';
  try {
    const result = await api("/api/collections");
    renderCollections(result.items || []);
  } catch (error) {
    container.innerHTML = "";
    showAlert(error.message);
  }
}
function renderCollections(items) {
  const container = $("#collections");
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = '<div class="col-12"><div class="feature-card empty-state"><div class="fs-2 mb-2">🗂️</div><strong>No collections yet</strong><div class="small mt-1">Create your first collection above.</div></div></div>';
    return;
  }
  items.forEach(item => {
    const col = document.createElement("div"); col.className = "col-sm-6 col-xl-3";
    const card = document.createElement("button"); card.type = "button";
    card.className = `collection-card text-start w-100 ${activeCollection === item.name ? "selected" : ""}`;
    const top = document.createElement("div"); top.className = "d-flex justify-content-between align-items-start mb-3";
    const icon = document.createElement("div"); icon.className = "collection-icon"; icon.textContent = "▰";
    const arrow = document.createElement("span"); arrow.className = "text-secondary"; arrow.textContent = "↗";
    top.append(icon, arrow);
    const title = document.createElement("div"); title.className = "fw-bold text-break"; title.textContent = item.name;
    const desc = document.createElement("div"); desc.className = "small text-secondary mt-1"; desc.textContent = "Open collection";
    card.append(top, title, desc);
    card.addEventListener("click", () => selectCollection(item.name));
    col.appendChild(card); container.appendChild(col);
  });
}
async function createCollection() {
  const input = $("#collectionName");
  const name = input.value.trim();
  if (!name) return showAlert("Enter a collection name.", "warning");
  try {
    clearAlert();
    await api("/api/collections", { method: "POST", body: JSON.stringify({ name }) });
    input.value = "";
    await loadCollections();
    await selectCollection(name);
    showAlert(`Collection “${name}” is ready.`, "success");
  } catch (error) { showAlert(error.message); }
}
async function selectCollection(name) {
  activeCollection = name;
  $("#selectedCollection").textContent = name;
  $("#documentsPanel").classList.remove("d-none");
  renderCollectionsFromCurrentSelection();
  const list = $("#documents"); list.innerHTML = '<div class="empty-state">Loading documents…</div>';
  try {
    const result = await api(`/api/collections/${encodeURIComponent(name)}/documents`);
    renderDocuments(result.items || []);
  } catch (error) { list.innerHTML = ""; showAlert(error.message); }
}
function renderCollectionsFromCurrentSelection() { loadCollections(); }
function renderDocuments(items) {
  const container = $("#documents"); container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = '<div class="empty-state"><div class="fs-2 mb-2">{ }</div><strong>No JSON documents yet</strong><div class="small mt-1">Create one to get started.</div></div>';
    return;
  }
  items.forEach(item => {
    const row = document.createElement("div"); row.className = "document-row";
    const info = document.createElement("div"); info.className = "min-w-0";
    const title = document.createElement("div"); title.className = "document-title"; title.textContent = item.name;
    const sub = document.createElement("div"); sub.className = "document-sub"; sub.textContent = item.modifiedTime ? `Updated ${new Date(item.modifiedTime).toLocaleString()}` : `ID: ${item.id}`;
    info.append(title, sub);
    const actions = document.createElement("div"); actions.className = "d-flex gap-2 flex-shrink-0";
    const view = document.createElement("button"); view.className = "btn btn-sm btn-outline-secondary"; view.textContent = "View / edit";
    view.addEventListener("click", () => editDocument(item.id));
    const del = document.createElement("button"); del.className = "btn btn-sm btn-outline-danger"; del.textContent = "Delete";
    del.addEventListener("click", () => deleteDocument(item.id, item.name));
    actions.append(view, del); row.append(info, actions); container.appendChild(row);
  });
}
function openDocumentEditor(data = null, id = null) {
  editingDocumentId = id;
  $("#documentModalTitle").textContent = id ? "Edit document" : "New document";
  $("#jsonError").textContent = "";
  $("#jsonEditor").value = data ? JSON.stringify(data, null, 2) : JSON.stringify({ title: "My document", description: "", tags: [] }, null, 2);
  modalInstance.show();
}
async function editDocument(id) {
  try {
    const result = await api(`/api/collections/${encodeURIComponent(activeCollection)}/documents/${encodeURIComponent(id)}`);
    openDocumentEditor(result.data, id);
  } catch (error) { showAlert(error.message); }
}
async function saveDocument() {
  let data;
  try {
    data = JSON.parse($("#jsonEditor").value);
    if (!data || Array.isArray(data) || typeof data !== "object") throw new Error("The top-level JSON value must be an object.");
  } catch (error) { $("#jsonError").textContent = `Invalid JSON: ${error.message}`; return; }
  const button = $("#saveDocumentBtn"); button.disabled = true; button.textContent = "Saving…";
  try {
    if (editingDocumentId) {
      await api(`/api/collections/${encodeURIComponent(activeCollection)}/documents/${encodeURIComponent(editingDocumentId)}`, { method: "PATCH", body: JSON.stringify({ data }) });
    } else {
      await api(`/api/collections/${encodeURIComponent(activeCollection)}/documents`, { method: "POST", body: JSON.stringify({ data }) });
    }
    modalInstance.hide();
    await selectCollection(activeCollection);
    showAlert("Document saved successfully.", "success");
  } catch (error) { $("#jsonError").textContent = error.message; }
  finally { button.disabled = false; button.textContent = "Save document"; }
}
async function deleteDocument(id, name) {
  if (!confirm(`Delete ${name}? This removes the file from your Google Drive.`)) return;
  try {
    await api(`/api/collections/${encodeURIComponent(activeCollection)}/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
    await selectCollection(activeCollection);
    showAlert("Document deleted.", "success");
  } catch (error) { showAlert(error.message); }
}
async function logout() {
  try { await api("/auth/logout", { method: "POST", body: "{}" }); location.href = "/"; }
  catch (error) { showAlert(error.message); }
}
