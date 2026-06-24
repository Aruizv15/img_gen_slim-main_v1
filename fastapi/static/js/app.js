/* ============================================================
   BatchApp Frontend — app.js
   ============================================================ */

const API_BASE = window.API_BASE || 'https://batchapp-frontend.onrender.com';
const IMGS_PER_PAGE = 4;
const POLL_INTERVAL = 5000;

/* ── Estado global ── */
let uploadedFiles  = [];   // { name, url, file }
let csvFile        = null; // File object del CSV/Excel
let generatedImgs  = [];   // [{ filename, url, state, vreproID }]
let currentPage    = 0;
let selectedIdx    = null;
let pollTimer      = null;

/* ── Estado multi-modelo (CSV) ── */
let csvModels      = [];   // [{ vreproID, age, skinTone, ... }]
let modelImages    = {};   // { vreproID: [{ name, url, file }] }
let modelResults   = {};   // { vreproID: [generatedImg] }
let vreproMap      = {};   // { filename: vreproID }
let assignedFiles  = new Set(); // filenames already assigned to a model
let seqRunning     = false;
let seqCancelled   = false;
let activeVreproID = null;
let continueResolve = null; // resuelve la promesa de "esperar al usuario"

/* ============================================================
   UTILIDADES
   ============================================================ */
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 3500);
}

function setStatus(online) {
  const dot  = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  dot.className   = 'status-dot ' + (online ? 'online' : 'offline');
  text.textContent = online ? 'Servidor en línea' : 'Servidor desconectado';
  text.style.color = online ? '#4a4' : '#a44';
}

/* ============================================================
   HEALTH CHECK
   ============================================================ */
async function checkHealth() {
  try {
    const res  = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(4000) });
    const data = await res.json();
    setStatus(true);
    document.getElementById('server-info').textContent =
      `FastAPI: OK\nComfyUI: ${data.comfyui_status || '?'}`;
  } catch {
    setStatus(false);
    document.getElementById('server-info').textContent = 'Sin conexión';
  }
}

/* ============================================================
   CSV — PARSING & CARGA
   ============================================================ */
document.getElementById('csv-input').addEventListener('change', function () {
  if (this.files[0]) loadCsv(this.files[0]);
  this.value = '';
});

function parseCSVContent(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const sep     = lines[0].includes('\t') ? '\t' : ',';
  const headers = lines[0].split(sep).map(h => h.trim());
  return lines.slice(1)
    .filter(l => l.trim())
    .map(line => {
      const vals = line.split(sep);
      const obj  = {};
      headers.forEach((h, i) => { obj[h] = (vals[i] || '').trim(); });
      return obj;
    });
}

function loadCsv(file) {
  csvFile = file;
  const zone = document.getElementById('csv-zone');
  zone.classList.add('loaded');
  document.getElementById('csv-text').textContent = file.name;
  showToast(`CSV cargado: ${file.name}`, 'success');

  const reader = new FileReader();
  
  if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, { type: 'array' });
      const sheet = workbook.Sheets[workbook.SheetNames[0]];
      csvModels = XLSX.utils.sheet_to_json(sheet);
      csvModels = csvModels.map(row => {
        const normalized = {};
        Object.keys(row).forEach(k => { normalized[k.trim()] = String(row[k] || '').trim(); });
        return normalized;
      });
      matchImagesToModels();
      renderModelList();
      updateUploadBadge();
      if (csvModels.length > 0) {
        showToast(`${csvModels.length} modelo(s) detectado(s)`, 'success');
      }
    };
    reader.readAsArrayBuffer(file);
  } else {
    reader.onload = (e) => {
      csvModels = parseCSVContent(e.target.result);
      matchImagesToModels();
      renderModelList();
      updateUploadBadge();
      if (csvModels.length > 0) {
        showToast(`${csvModels.length} modelo(s) detectado(s)`, 'success');
      }
    };
    reader.readAsText(file);
  }
  updateUploadBadge();
}

/* ============================================================
   PANEL IZQUIERDO — IMÁGENES
   ============================================================ */
function openFilePicker() {
  document.getElementById('file-input').click();
}

document.getElementById('file-input').addEventListener('change', function () {
  addFiles(this.files);
  this.value = '';
});

const dropArea = document.getElementById('drop-area');
dropArea.addEventListener('dragover',  e => { e.preventDefault(); dropArea.classList.add('dragover'); });
dropArea.addEventListener('dragleave', ()  => dropArea.classList.remove('dragover'));
dropArea.addEventListener('drop',      e  => {
  e.preventDefault();
  dropArea.classList.remove('dragover');
  addFiles(e.dataTransfer.files);
});

function addFiles(files) {
  Array.from(files).forEach(file => {
    if (!file.type.startsWith('image/')) return;
    const url = URL.createObjectURL(file);
    uploadedFiles.push({ name: file.name, url, file });
  });
  matchImagesToModels();
  renderUpload();
}

function removeFile(index) {
  URL.revokeObjectURL(uploadedFiles[index].url);
  uploadedFiles.splice(index, 1);
  matchImagesToModels();
  renderUpload();
}

/* Asigna cada imagen subida al modelo cuyo vreproID aparece al inicio del filename */
function matchImagesToModels() {
  if (!csvModels.length) return;
  modelImages = {};
  csvModels.forEach(m => { modelImages[m.vreproID] = []; });
  uploadedFiles.forEach(f => {
    const match = csvModels.find(m => f.name.startsWith(m.vreproID));
    if (match) modelImages[match.vreproID].push(f);
  });
  renderModelList();
}

function renderUpload() {
  const grid    = document.getElementById('upload-grid');
  const addSlot = document.getElementById('add-slot');
  Array.from(grid.querySelectorAll('.uslot')).forEach(el => el.remove());

  uploadedFiles.forEach((f, i) => {
    const slot = document.createElement('div');
    slot.className = 'uslot';

    const img = document.createElement('img');
    img.src = f.url; img.alt = f.name;
    slot.appendChild(img);

    const overlay  = document.createElement('div');
    overlay.className = 'uoverlay';
    const nameEl   = document.createElement('span');
    nameEl.className = 'uname';
    nameEl.textContent = f.name.length > 14 ? f.name.slice(0, 12) + '…' : f.name;
    overlay.appendChild(nameEl);
    slot.appendChild(overlay);

    const num = document.createElement('span');
    num.className  = 'unum';
    num.textContent = '#' + (i + 1);
    slot.appendChild(num);

    const del = document.createElement('button');
    del.className  = 'udelete'; del.title = 'Eliminar'; del.textContent = '✕';
    del.onclick    = e => { e.stopPropagation(); removeFile(i); };
    slot.appendChild(del);

    grid.insertBefore(slot, addSlot);
  });

  updateUploadBadge();
}

function updateUploadBadge() {
  const total = uploadedFiles.length + (csvFile ? 1 : 0);
  document.getElementById('upload-badge').textContent =
    total + ' archivo' + (total !== 1 ? 's' : '');
}

/* ============================================================
   LISTA DE MODELOS (panel izquierdo, bajo CSV)
   ============================================================ */
function renderModelList() {
  const container = document.getElementById('model-list-container');
  if (!container) return;

  if (!csvModels.length) {
    container.style.display = 'none';
    return;
  }
  container.style.display = 'flex';
  container.innerHTML = '';

  csvModels.forEach(m => {
    const imgs    = (modelImages[m.vreproID] || []).length;
    const results = modelResults[m.vreproID];

    let statusClass = 'waiting';
    let statusText  = 'Pendiente';
    if (activeVreproID === m.vreproID) {
      statusClass = 'processing';
      statusText  = 'Procesando…';
    } else if (results) {
      statusClass = 'done';
      statusText  = `${results.length} gen.`;
    }

    const card = document.createElement('div');
    card.className = 'model-card';
    card.innerHTML = `
      <span class="model-id">${m.vreproID}</span>
      <span class="model-imgs-count">${imgs} img${imgs !== 1 ? 's' : ''}</span>
      <span class="model-status ${statusClass}">${statusText}</span>
    `;
    container.appendChild(card);
  });
}

/* ============================================================
   SUBIR AL SERVIDOR
   ============================================================ */
async function uploadToServer() {
  if (uploadedFiles.length === 0 && !csvFile) {
    showToast('Agrega imágenes o un CSV antes de subir.', 'error');
    return;
  }

  const btn      = document.getElementById('btn-upload-server');
  const progress = document.getElementById('upload-progress');
  const fill     = document.getElementById('progress-fill');
  const text     = document.getElementById('progress-text');

  btn.disabled = true;
  progress.style.display = 'flex';
  fill.style.width = '10%';
  text.textContent = 'Preparando archivos...';

  try {
    const formData = new FormData();
    uploadedFiles.forEach(f => formData.append('images', f.file));
    if (csvFile) formData.append('csv', csvFile);

    fill.style.width = '40%';
    text.textContent = 'Subiendo al servidor...';

    const res = await fetch(`${API_BASE}/upload_images`, { method: 'POST', body: formData });

    fill.style.width = '90%';
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    fill.style.width = '100%';
    text.textContent = 'Completado';
    showToast('Archivos subidos correctamente al servidor.', 'success');
    setTimeout(() => { progress.style.display = 'none'; fill.style.width = '0%'; }, 1500);
  } catch (err) {
    fill.style.width = '100%';
    fill.style.background = '#a33';
    text.textContent = 'Error: ' + err.message;
    showToast('Error al subir: ' + err.message, 'error');
    setTimeout(() => {
      progress.style.display = 'none';
      fill.style.width = '0%';
      fill.style.background = '';
    }, 3000);
  } finally {
    btn.disabled = false;
  }
}

/* Sube solo las imágenes de un modelo específico (para ejecución secuencial).
   Renombra cada archivo agregando el modo al nombre:
   OVOD02562.jpg  →  OVOD02562fullbody.jpg  o  OVOD02562Portrait.jpg */
async function uploadModelImages(vreproID) {
  const images   = modelImages[vreproID] || [];
  const modeText = document.querySelector('.mode-btn.active').textContent.trim();
  const suffix   = modeText.toLowerCase() === 'fullbody' ? 'fullbody' : 'Portrait';

  const formData = new FormData();
  images.forEach(f => {
    const dotIdx  = f.name.lastIndexOf('.');
    const base    = dotIdx !== -1 ? f.name.slice(0, dotIdx) : f.name;
    const ext     = dotIdx !== -1 ? f.name.slice(dotIdx)    : '';
    const newName = base + suffix + ext;
    const renamed = new File([f.file], newName, { type: f.file.type });
    formData.append('images', renamed);
  });

  const res = await fetch(`${API_BASE}/upload_images`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error(`Error subiendo imágenes de ${vreproID}`);
}

/* ============================================================
   PANEL DERECHO — IMÁGENES GENERADAS
   ============================================================ */
async function fetchGeneratedImages() {
  try {
    const res  = await fetch(`${API_BASE}/list_images`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const filenames = Array.isArray(data) ? data : (data.images || []);

    // Preservar estados y vreproID existentes
    const stateMap = {};
    generatedImgs.forEach(g => { stateMap[g.filename] = g.state; });

    generatedImgs = filenames.map(fn => ({
      filename: fn,
      url:      `${API_BASE}/images/${fn}`,
      state:    stateMap[fn] || 'pending',
      vreproID: vreproMap[fn] || null,
    }));

    document.getElementById('gen-badge').textContent = generatedImgs.length + ' generadas';
    document.getElementById('total-count').textContent = generatedImgs.length;

    const tp = totalPages();
    if (currentPage >= tp && tp > 0) currentPage = tp - 1;
    if (tp === 0) currentPage = 0;

    renderGen();
    updateApprCount();
  } catch (err) {
    console.warn('Error al obtener imágenes:', err.message);
  }
}

/* Devuelve sólo los filenames nuevos desde la última vez que se llamó (para ejecución secuencial) */
async function fetchNewImages() {
  const res       = await fetch(`${API_BASE}/list_images`);
  const data      = await res.json();
  const filenames = Array.isArray(data) ? data : (data.images || []);
  const newFns    = filenames.filter(fn => !assignedFiles.has(fn));

  newFns.forEach(fn => {
    assignedFiles.add(fn);
    vreproMap[fn] = activeVreproID;
  });

  return newFns.map(fn => ({
    filename: fn,
    url:      `${API_BASE}/images/${fn}`,
    state:    'pending',
    vreproID: activeVreproID,
  }));
}

function totalPages() { return Math.ceil(generatedImgs.length / IMGS_PER_PAGE); }

function renderGen() {
  const area = document.getElementById('page-area');
  area.innerHTML = '';

  if (generatedImgs.length === 0) {
    area.innerHTML = `<div class="empty-state"><i class="ti ti-photo-off"></i><span>Sin imágenes generadas aún</span></div>`;
    document.getElementById('page-info').textContent = '—';
    document.getElementById('prev-btn').disabled = true;
    document.getElementById('next-btn').disabled = true;
    document.getElementById('page-dots').innerHTML = '';
    return;
  }

  const start = currentPage * IMGS_PER_PAGE;
  const end   = Math.min(start + IMGS_PER_PAGE, generatedImgs.length);

  for (let i = start; i < end; i++) {
    const { filename, url, state, vreproID } = generatedImgs[i];
    const slot = document.createElement('div');
    slot.className = 'gslot ' + state + (selectedIdx === i ? ' selected' : '');
    slot.onclick   = () => { selectedIdx = (selectedIdx === i ? null : i); renderGen(); };

    const img = document.createElement('img');
    img.src  = url;
    img.alt  = filename;
    img.onerror = () => {
      slot.querySelector('img')?.remove();
      const sh = document.createElement('div');
      sh.className = 'shimmer';
      sh.style.cssText = 'width:60%;height:50%;';
      slot.insertBefore(sh, slot.firstChild);
    };
    slot.appendChild(img);

    // Badge con vreproID (si está asignado)
    if (vreproID) {
      const badge = document.createElement('div');
      badge.className  = 'vrepro-badge';
      badge.textContent = vreproID.length > 10 ? vreproID.slice(-10) : vreproID;
      slot.appendChild(badge);
    }

    if (state === 'approved') {
      const mark = document.createElement('div');
      mark.className  = 'gmark a'; mark.textContent = '✓';
      slot.appendChild(mark);
    } else if (state === 'discarded') {
      const mark = document.createElement('div');
      mark.className  = 'gmark d'; mark.textContent = '✕';
      slot.appendChild(mark);
    }

    const ov  = document.createElement('div');
    ov.className = 'goverlay';
    const lbl = document.createElement('span');
    lbl.className  = 'gname';
    lbl.textContent = filename.length > 20 ? filename.slice(0, 18) + '…' : filename;
    ov.appendChild(lbl);
    slot.appendChild(ov);

    area.appendChild(slot);
  }

  const tp = totalPages();
  document.getElementById('page-info').textContent = 'Hoja ' + (currentPage + 1) + ' de ' + tp;
  document.getElementById('prev-btn').disabled = currentPage === 0;
  document.getElementById('next-btn').disabled = currentPage >= tp - 1;

  const dots = document.getElementById('page-dots');
  dots.innerHTML = '';
  for (let p = 0; p < tp; p++) {
    const d = document.createElement('div');
    d.className = 'pdot' + (p === currentPage ? ' active' : '');
    d.onclick   = () => { currentPage = p; selectedIdx = null; renderGen(); };
    dots.appendChild(d);
  }
}

function changePage(dir) {
  const np = currentPage + dir;
  const tp = totalPages();
  if (np >= 0 && np < tp) { currentPage = np; selectedIdx = null; renderGen(); }
}

function approveSelected() {
  if (selectedIdx === null) { showToast('Selecciona una imagen primero.', 'error'); return; }
  generatedImgs[selectedIdx].state = 'approved';
  selectedIdx = null;
  renderGen();
  updateApprCount();
}

function discardSelected() {
  if (selectedIdx === null) { showToast('Selecciona una imagen primero.', 'error'); return; }
  generatedImgs[selectedIdx].state = 'discarded';
  selectedIdx = null;
  renderGen();
  updateApprCount();
}

function updateApprCount() {
  const approved = generatedImgs.filter(g => g.state === 'approved').length;
  document.getElementById('appr-count').textContent = approved;
}

/* ============================================================
   DESCARGAR APROBADAS
   ============================================================ */
async function downloadApproved() {
  const approved = generatedImgs.filter(g => g.state === 'approved');
  if (approved.length === 0) { showToast('No hay imágenes aprobadas aún.', 'error'); return; }

  showToast(`Descargando ${approved.length} imagen(es)...`);
  for (const img of approved) {
    try {
      const res  = await fetch(img.url);
      const blob = await res.blob();
      const a    = document.createElement('a');
      a.href     = URL.createObjectURL(blob);
      a.download = img.filename;
      a.click();
      URL.revokeObjectURL(a.href);
      await new Promise(r => setTimeout(r, 300));
    } catch {
      console.warn('No se pudo descargar:', img.filename);
    }
  }
  showToast(`${approved.length} imagen(es) descargada(s).`, 'success');
}

/* ============================================================
   LIMPIAR SERVIDOR
   ============================================================ */
async function clearServerImages() {
  if (!confirm('¿Eliminar todas las imágenes del servidor? Esta acción no se puede deshacer.')) return;
  try {
    const res = await fetch(`${API_BASE}/clear_images`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    // Limpiar estado local
    generatedImgs  = [];
    selectedIdx    = null;
    currentPage    = 0;
    vreproMap      = {};
    assignedFiles  = new Set();
    modelResults   = {};

    renderGen();
    renderModelList();
    updateApprCount();
    document.getElementById('gen-badge').textContent   = '0 generadas';
    document.getElementById('total-count').textContent = '0';
    showToast('Imágenes del servidor eliminadas.', 'success');
  } catch (err) {
    showToast('Error al limpiar: ' + err.message, 'error');
  }
}

/* ============================================================
   EJECUCIÓN — MODELO ÚNICO
   ============================================================ */
async function startSingleExecution() {
  const mode    = document.querySelector('.mode-btn.active').textContent.trim().toLowerCase();
  const cycles  = document.getElementById(mode === 'fullbody' ? 'fb-cycles' : 'pt-cycles').value;
  const donors  = document.getElementById('model-list').value;
  const usePose    = document.getElementById('cb-pose').classList.contains('on');
  const useHands   = document.getElementById('cb-hands').classList.contains('on');
  const useAmateur = document.getElementById('cb-amateur').classList.contains('on');

  const params = new URLSearchParams({
    generation_type:    mode,
    max_cycles:         cycles,
    donor_list:         donors,
    use_pose:           usePose,
    use_hands_refiner:  useHands,
    use_amateur_effect: useAmateur,
  });

  const res  = await fetch(`${API_BASE}/jobs?${params}`, { method: 'POST' });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

  showToast('Job iniciado: ' + data.job_id.slice(0, 8), 'success');
  startPolling();
}

/* ============================================================
   EJECUCIÓN — MULTI-MODELO SECUENCIAL (CSV)
   ============================================================ */

/* Espera hasta que el job actual termine (polling cada 3s) */
async function waitForJobDone() {
  while (true) {
    await new Promise(r => setTimeout(r, 3000));
    try {
      const res = await fetch(`${API_BASE}/jobs/current`);
      const job = await res.json();
      if (job.status === 'done' || job.status === 'error' || job.status === 'idle') return job;
    } catch { /* sigue esperando */ }
  }
}

/* El usuario presiona "Continuar" → desbloquea la promesa de espera */
function continueToNextModel() {
  if (continueResolve) {
    continueResolve();
    continueResolve = null;
  }
}

/* Pausa el bucle hasta que el usuario presione Continuar (o se cancele) */
function waitForUserContinue() {
  return new Promise(resolve => {
    continueResolve = resolve;
    document.getElementById('btn-continue').style.display = 'flex';
  });
}

/* Actualiza la barra de progreso secuencial */
function updateSeqProgress(current, total, vreproID, state, nextVreproID) {
  const div = document.getElementById('seq-progress');
  const sts = document.getElementById('seq-status');
  const btn = document.getElementById('btn-continue');
  if (!div || !sts || !btn) return;

  div.style.display = 'flex';
  btn.style.display  = 'none';

  if (state === 'processing') {
    sts.innerHTML = `
      <span class="seq-step">Modelo ${current} de ${total}</span>
      <span class="seq-id processing">${vreproID}</span>
      <span class="seq-state">Generando imágenes…</span>`;
  } else if (state === 'waiting') {
    sts.innerHTML = `
      <span class="seq-step">Modelo ${current} de ${total}</span>
      <span class="seq-id done">✓ ${vreproID}</span>
      <span class="seq-arrow">→</span>
      <span class="seq-next">Siguiente: <strong>${nextVreproID}</strong></span>`;
    btn.style.display = 'flex';
  } else if (state === 'done') {
    sts.innerHTML = `
      <span class="seq-step">${total} de ${total} completados</span>
      <span class="seq-id done">✓ ${vreproID}</span>`;
  }
}

function hideSeqProgress() {
  const div = document.getElementById('seq-progress');
  if (div) div.style.display = 'none';
}

async function executeModelsSequentially() {
  seqRunning     = true;
  seqCancelled   = false;
  assignedFiles  = new Set();
  vreproMap      = {};
  modelResults   = {};
  generatedImgs  = [];
  renderGen();

  // Subir CSV al servidor primero
  if (csvFile) {
    const fd = new FormData();
    fd.append('csv', csvFile);
    await fetch(`${API_BASE}/upload_images`, { method: 'POST', body: fd });
  }

  const mode    = document.querySelector('.mode-btn.active').textContent.trim().toLowerCase();
  const cycles  = document.getElementById(mode === 'fullbody' ? 'fb-cycles' : 'pt-cycles').value;
  const usePose    = document.getElementById('cb-pose').classList.contains('on');
  const useHands   = document.getElementById('cb-hands').classList.contains('on');
  const useAmateur = document.getElementById('cb-amateur').classList.contains('on');

  const queue = csvModels.filter(m => (modelImages[m.vreproID] || []).length > 0);

  if (queue.length === 0) {
    showToast('Ningún modelo tiene imágenes asignadas. Sube fotos con el nombre del vreproID.', 'error');
    seqRunning = false;
    return;
  }

  showToast(`Iniciando ejecución secuencial: ${queue.length} modelo(s)`, 'success');

  for (let i = 0; i < queue.length; i++) {
    if (seqCancelled) break;

    const model    = queue[i];
    activeVreproID = model.vreproID;
    renderModelList();
    updateSeqProgress(i + 1, queue.length, model.vreproID, 'processing');

    // Subir imágenes del modelo actual
    try {
      await uploadModelImages(model.vreproID);
    } catch (err) {
      showToast(`Error subiendo imágenes de ${model.vreproID}: ${err.message}`, 'error');
      continue;
    }

    // Iniciar job para este modelo
    const params = new URLSearchParams({
      generation_type:    mode,
      max_cycles:         cycles,
      donor_list:         model.vreproID,
      use_pose:           usePose,
      use_hands_refiner:  useHands,
      use_amateur_effect: useAmateur,
    });

    const jobRes = await fetch(`${API_BASE}/jobs?${params}`, { method: 'POST' });
    if (!jobRes.ok) {
      const err = await jobRes.json().catch(() => ({}));
      showToast(`Error iniciando job para ${model.vreproID}: ${err.detail || '?'}`, 'error');
      continue;
    }

    startPolling();
    const jobResult = await waitForJobDone();
    stopPolling();

    if (jobResult.status === 'error') {
      showToast(`Error en job de ${model.vreproID}: ${jobResult.error || '?'}`, 'error');
    }

    // Pausa para asegurar que los archivos están escritos
    await new Promise(r => setTimeout(r, 1000));

    const newImgs = await fetchNewImages();
    modelResults[model.vreproID] = newImgs;
    generatedImgs.push(...newImgs);

    activeVreproID = null;
    renderModelList();
    renderGen();
    updateApprCount();

    showToast(`✓ ${model.vreproID}: ${newImgs.length} imagen(es) lista(s). Revisa y descarga.`, 'success');

    // Si hay más modelos: pausar y esperar que el usuario continúe
    if (i < queue.length - 1 && !seqCancelled) {
      updateSeqProgress(i + 1, queue.length, model.vreproID, 'waiting', queue[i + 1].vreproID);
      await waitForUserContinue();
      if (seqCancelled) break;
    } else if (i === queue.length - 1) {
      updateSeqProgress(i + 1, queue.length, model.vreproID, 'done');
    }
  }

  seqRunning     = false;
  seqCancelled   = false;
  continueResolve = null;
  if (!seqCancelled) {
    showToast(`Proceso completado. ${generatedImgs.length} imagen(es) en total.`, 'success');
  }
  setTimeout(hideSeqProgress, 4000);
}

/* ============================================================
   EJECUCIÓN — ENTRADA PRINCIPAL
   ============================================================ */
async function startExecution() {
  if (seqRunning) {
    showToast('Ya hay una ejecución secuencial en curso.', 'error');
    return;
  }

  // Si hay modelos del CSV con imágenes asignadas → ejecución secuencial
  const hasModelImages = csvModels.length > 0 &&
    csvModels.some(m => (modelImages[m.vreproID] || []).length > 0);

  if (hasModelImages) {
    await executeModelsSequentially();
  } else {
    // Ejecución normal (un solo batch)
    try {
      await startSingleExecution();
    } catch (err) {
      showToast('Error al iniciar: ' + err.message, 'error');
    }
  }
}

async function stopExecution() {
  // Cancelar ejecución secuencial (incluso si está en pausa esperando al usuario)
  seqCancelled = true;
  if (continueResolve) {
    continueResolve();
    continueResolve = null;
  }
  hideSeqProgress();

  try {
    await fetch(`${API_BASE}/interrupt`, { method: 'POST' });
    showToast('Ejecución interrumpida.', 'success');
  } catch (err) {
    showToast('Error al detener: ' + err.message, 'error');
  }
  stopPolling();
  seqRunning     = false;
  activeVreproID = null;
  renderModelList();
}

/* ============================================================
   POLLING AUTOMÁTICO DE IMÁGENES
   ============================================================ */
function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(fetchGeneratedImages, POLL_INTERVAL);
}

function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}


function setMode(btn) {
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function toggleCb(el) {
  el.classList.toggle('on');
}

/* ============================================================
   INIT
   ============================================================ */
checkHealth();
setInterval(checkHealth, 30000);
fetchGeneratedImages();
startPolling();
