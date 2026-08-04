/* ============================================================
   BatchApp Frontend — app.js
   Nota: API_BASE, authFetch, y todo el manejo de login/sesion
   viven en auth.js (debe cargarse ANTES que este archivo).
   ============================================================ */
const IMGS_PER_PAGE = 4;
const POLL_INTERVAL = 5000;

/* ── Estado global ── */
let uploadedFiles  = [];   // { name, url, file }
let csvFile        = null; // File object del CSV/Excel
let generatedImgs  = [];   // [{ filename, url, state, vreproID }]
let currentPage    = 0;
let selectedIndices = new Set();
let currentSessionDonors = null; // null = mostrar todo el historial; Set = filtrar solo estos donantes
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
const csvInputEl = document.getElementById('csv-input');
if (csvInputEl) {
  csvInputEl.addEventListener('change', function () {
    if (this.files[0]) loadCsv(this.files[0]);
    this.value = '';
  });
} else {
  console.warn('[app.js] No se encontro el elemento #csv-input en el HTML.');
}

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

const fileInputEl = document.getElementById('file-input');
if (fileInputEl) {
  fileInputEl.addEventListener('change', function () {
    addFiles(this.files);
    this.value = '';
  });
} else {
  console.warn('[app.js] No se encontro el elemento #file-input en el HTML.');
}

const dropArea = document.getElementById('drop-area');
if (dropArea) {
  dropArea.addEventListener('dragover',  e => { e.preventDefault(); dropArea.classList.add('dragover'); });
  dropArea.addEventListener('dragleave', ()  => dropArea.classList.remove('dragover'));
  dropArea.addEventListener('drop',      e  => {
    e.preventDefault();
    dropArea.classList.remove('dragover');
    addFiles(e.dataTransfer.files);
  });
} else {
  console.warn('[app.js] No se encontro el elemento #drop-area en el HTML. La zona de arrastrar-y-soltar no estara disponible, pero el resto de la app sigue funcionando.');
}

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

    const res = await authFetch(`${API_BASE}/upload_images`, { method: 'POST', body: formData });

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

  const res = await authFetch(`${API_BASE}/upload_images`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error(`Error subiendo imágenes de ${vreproID}`);
}

/* ============================================================
   PANEL DERECHO — IMÁGENES GENERADAS
   ============================================================ */
/* Extrae el vreproID del nombre de archivo (patron: "{vreproID}_00001_.png").
   Sirve como respaldo confiable cuando vreproMap no lo tiene (por ejemplo,
   despues de recargar la pagina, o con imagenes de sesiones anteriores
   detectadas por el polling automatico). */
function extractVreproID(filename) {
  const match = filename.match(/^(.+?)_\d+_\.\w+$/);
  return match ? match[1] : null;
}

async function fetchGeneratedImages() {
  try {
    const res  = await authFetch(`${API_BASE}/list_images_b2`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items = data.images || [];

    // El servidor YA devuelve solo la corrida mas reciente por
    // donante+tipo (de forma permanente, sin importar el navegador ni
    // si se recarga la pagina) -- aqui solo falta acotar a los donantes
    // de la sesion actual (para no mezclar con otros donantes que no se
    // esten trabajando ahora) y al modo activo (Fullbody/Portrait).
    const itemsPorSesion = currentSessionDonors
      ? items.filter(it => currentSessionDonors.has(it.vreproID))
      : items;

    // Filtro ESTRICTO por tipo: en modo Portrait solo se muestran fotos
    // etiquetadas como portrait, nunca fullbody (ni al reves). Las fotos
    // "legacy" (de antes de separar por tipo, sin etiqueta) ya NO se
    // muestran mezcladas automaticamente -- se estaban colando fotos
    // viejas de un tipo mientras se trabajaba en el otro, justo la
    // confusion que este filtro estricto evita.
    const modoActivo = document.querySelector('.mode-btn.active')?.textContent.trim().toLowerCase() || 'fullbody';
    const itemsFiltrados = itemsPorSesion.filter(it =>
      it.generationType === modoActivo
    );

    // Preservar estados existentes. Clave compuesta vreproID::filename:
    // indexar solo por filename hacia que aprobar la foto de un donante
    // "contagiara" el estado a la foto de otro donante que por casualidad
    // tuviera el mismo nombre de archivo.
    const stateMap = {};
    generatedImgs.forEach(g => { stateMap[`${g.vreproID}::${g.filename}`] = g.state; });

    generatedImgs = itemsFiltrados.map(({ filename, vreproID, generationType, b2Path }) => ({
      filename,
      // <img src> no puede enviar la cabecera Authorization, asi que el
      // token va como query param. view_from_b2 acepta ambas formas
      // (ver require_login_flexible en auth.py) justo por este motivo.
      // Se usa b2Path tal cual lo entrega el servidor (la ruta real en
      // Backblaze) en vez de reconstruirla a mano, para no desincronizarse
      // si el formato de carpetas cambia en el futuro.
      url:      `${API_BASE}/view_from_b2/${b2Path}?token=${encodeURIComponent(sessionToken || '')}`,
      state:    stateMap[`${vreproID}::${filename}`] || 'pending',
      vreproID: vreproID || extractVreproID(filename),
      generationType: generationType || 'legacy',
      b2Path,
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
  const res       = await authFetch(`${API_BASE}/list_images`);
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
    vreproID: activeVreproID || extractVreproID(fn),
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
    slot.className = 'gslot ' + state + (selectedIndices.has(i) ? ' selected' : '');
    slot.onclick   = () => {
      if (selectedIndices.has(i)) selectedIndices.delete(i);
      else selectedIndices.add(i);
      renderGen();
    };

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
    d.onclick   = () => { currentPage = p; renderGen(); };
    dots.appendChild(d);
  }
}

function changePage(dir) {
  const np = currentPage + dir;
  const tp = totalPages();
  if (np >= 0 && np < tp) { currentPage = np; renderGen(); }
}

function approveSelected() {
  if (selectedIndices.size === 0) { showToast('Selecciona al menos una imagen primero.', 'error'); return; }
  selectedIndices.forEach(idx => { generatedImgs[idx].state = 'approved'; });
  const count = selectedIndices.size;
  selectedIndices.clear();
  renderGen();
  updateApprCount();
  showToast(`${count} imagen(es) aprobada(s).`, 'success');
}

function discardSelected() {
  if (selectedIndices.size === 0) { showToast('Selecciona al menos una imagen primero.', 'error'); return; }
  selectedIndices.forEach(idx => { generatedImgs[idx].state = 'discarded'; });
  const count = selectedIndices.size;
  selectedIndices.clear();
  renderGen();
  updateApprCount();
  showToast(`${count} imagen(es) descartada(s).`, 'success');
}

/* ============================================================
   COMPARAR — todas las fotos generadas de un donante vs sus referencias
   ============================================================ */
async function openCompareModal() {
  // El donante a comparar se toma de la foto seleccionada si hay una, o
  // si no, de la primera foto visible en la pagina actual de la galeria.
  let vreproID = null;
  if (selectedIndices.size > 0) {
    vreproID = generatedImgs[[...selectedIndices][0]]?.vreproID;
  } else if (generatedImgs.length > 0) {
    const start = currentPage * IMGS_PER_PAGE;
    vreproID = generatedImgs[start]?.vreproID;
  }

  if (!vreproID) {
    showToast('No hay ninguna foto generada para comparar todavía.', 'error');
    return;
  }

  document.getElementById('compare-title').textContent = `Comparar — ${vreproID}`;
  document.getElementById('compare-modal').style.display = 'flex';

  renderCompareGenerated(vreproID);

  const refContainer = document.getElementById('compare-ref-container');
  refContainer.innerHTML = '<span style="color:#555;font-size:12px;">Cargando...</span>';
  try {
    const res = await authFetch(`${API_BASE}/list_reference_images_b2/${vreproID}`);
    const data = await res.json();
    const refs = data.images || [];
    if (refs.length === 0) {
      refContainer.innerHTML = '<span style="color:#555;font-size:12px;">No se encontraron fotos de referencia para este donante.</span>';
      return;
    }
    refContainer.innerHTML = refs.map(r =>
      `<img src="${API_BASE}/view_reference_from_b2/${vreproID}/${r.filename}?token=${encodeURIComponent(sessionToken || '')}" style="max-height:220px;border-radius:6px;" />`
    ).join('');
  } catch (err) {
    refContainer.innerHTML = '<span style="color:#ff8a8a;font-size:12px;">Error cargando la referencia.</span>';
  }
}

function renderCompareGenerated(vreproID) {
  const container = document.getElementById('compare-gen-container');
  // Todas las fotos de ESTE donante que coincidan con el codigo OVOD,
  // dentro de lo que ya esta filtrado por modo (Fullbody/Portrait).
  const fotos = generatedImgs
    .map((img, idx) => ({ img, idx }))
    .filter(({ img }) => img.vreproID === vreproID);

  if (fotos.length === 0) {
    container.innerHTML = '<span style="color:#555;font-size:12px;">Sin fotos generadas para este donante en el modo actual.</span>';
    return;
  }

  container.innerHTML = '';
  fotos.forEach(({ img, idx }) => {
    const card = document.createElement('div');
    card.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:6px;';

    const borderColor = img.state === 'approved' ? '#2ecc71' : img.state === 'discarded' ? '#e74c3c' : '#333';
    card.innerHTML = `
      <img src="${img.url}" style="max-height:220px;border-radius:6px;border:2px solid ${borderColor};" />
      <div style="display:flex;gap:6px;">
        <button onclick="setCompareState(${idx}, 'approved')" style="background:#123c1e;border:1px solid #2ecc71;color:#7ee2a0;border-radius:5px;padding:3px 8px;font-size:11px;cursor:pointer;">✓ Aprobar</button>
        <button onclick="setCompareState(${idx}, 'discarded')" style="background:#3c1212;border:1px solid #e74c3c;color:#ff8a8a;border-radius:5px;padding:3px 8px;font-size:11px;cursor:pointer;">✕ Descartar</button>
      </div>
    `;
    container.appendChild(card);
  });
}

function setCompareState(idx, state) {
  if (!generatedImgs[idx]) return;
  generatedImgs[idx].state = state;
  renderCompareGenerated(generatedImgs[idx].vreproID);
  renderGen();
  updateApprCount();
}

function closeCompareModal() {
  document.getElementById('compare-modal').style.display = 'none';
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

  if (typeof JSZip === 'undefined') {
    showToast('Falta cargar JSZip en index.html. Ver instrucciones.', 'error');
    console.error('JSZip no esta disponible. Agrega <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script> en index.html antes de app.js.');
    return;
  }

  showToast(`Empaquetando ${approved.length} imagen(es)...`);
  const zip = new JSZip();
  const failed = [];

  // Contador independiente por donante+tipo, para numerar _c1, _c2, _c3...
  // (fullbody) y _p1, _p2, _p3... (portrait) segun el orden en que
  // aparecen las imagenes aprobadas.
  const contadores = {};

  for (const img of approved) {
    let success = false;
    for (let intento = 1; intento <= 3 && !success; intento++) {
      try {
        // Descarga directo de Backblaze (permanente), no de la carpeta
        // local del servidor (que se borra en cada reinicio de Render).
        const downloadUrl = img.b2Path
          ? `${API_BASE}/download_from_b2/${img.b2Path}`
          : img.url; // fallback si por alguna razon no hay b2Path asignado
        const res  = await authFetch(downloadUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        console.log(`[ZIP] ${img.filename} (intento ${intento}): ${blob.size} bytes, tipo: ${blob.type}`);
        if (blob.size === 0) {
          throw new Error('El archivo descargado esta vacio (0 bytes)');
        }

        // Estructura del ZIP:
        //   OVOD01234/fullbody/OVOD01234_c1.png, _c2.png, _c3.png...
        //   OVOD01234/portrait/OVOD01234_p1.png, _p2.png...
        const vreproID = img.vreproID || 'sin_codigo';
        const tipo = img.generationType === 'portrait' ? 'portrait' : 'fullbody';
        const prefijo = img.generationType === 'portrait' ? 'p' : 'c';
        const contadorKey = `${vreproID}::${tipo}`;
        contadores[contadorKey] = (contadores[contadorKey] || 0) + 1;
        const extMatch = img.filename.match(/\.[^.]+$/);
        const ext = extMatch ? extMatch[0] : '.png';
        const zipPath = `${vreproID}/${tipo}/${vreproID}_${prefijo}${contadores[contadorKey]}${ext}`;

        zip.file(zipPath, blob);
        success = true;
      } catch (err) {
        console.warn(`Intento ${intento}/3 fallo para ${img.filename}:`, err.message);
        if (intento < 3) {
          // Pausa antes de reintentar, dando tiempo a que Backblaze
          // se recupere si el fallo fue por demasiadas peticiones seguidas.
          await new Promise(r => setTimeout(r, 800));
        }
      }
    }
    if (!success) {
      failed.push(img.filename);
    }
    // Pausa pequeña entre cada imagen (incluso si tuvo exito), para no
    // saturar a Backblaze con peticiones demasiado rapidas seguidas.
    await new Promise(r => setTimeout(r, 250));
  }

  const zipBlob = await zip.generateAsync({ type: 'blob' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(zipBlob);
  a.download = `imagenes_aprobadas_${Date.now()}.zip`;
  a.click();
  URL.revokeObjectURL(a.href);

  if (failed.length > 0) {
    showToast(`ZIP descargado, pero ${failed.length} imagen(es) fallaron: ${failed.join(', ')}`, 'error');
  } else {
    showToast(`${approved.length} imagen(es) descargada(s) en un ZIP.`, 'success');
  }
}

/* ============================================================
   LIMPIAR SERVIDOR
   ============================================================ */
async function clearServerImages() {
  if (!confirm('¿Limpiar la vista local de imágenes? Esto NO borra nada de Backblaze (tus imágenes generadas siguen guardadas ahí para siempre).')) return;
  try {
    const res = await authFetch(`${API_BASE}/clear_images`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    // Limpiar estado local
    generatedImgs  = [];
    selectedIndices = new Set();
    currentPage    = 0;
    vreproMap      = {};
    assignedFiles  = new Set();
    modelResults   = {};
    // Antes: currentSessionDonors = null volvia a mostrar TODO el
    // historial de Backblaze (nunca se borra de ahi a proposito). Como el
    // polling automatico sigue consultando B2 de fondo, la galeria se
    // repoblaba sola segundos despues de "limpiar", pareciendo que el
    // boton no hacia nada. Con un Set vacio, el filtro sigue activo pero
    // no deja pasar ningun donante -- la galeria se queda vacia de verdad
    // hasta que se inicie una generacion nueva (que reasigna este valor
    // con los donantes reales en executeModelsSequentially).
    currentSessionDonors = new Set(); // vacio a proposito: oculta todo hasta la proxima generacion

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

  const res  = await authFetch(`${API_BASE}/jobs?${params}`, { method: 'POST' });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

  showToast('Job iniciado: ' + data.job_id.slice(0, 8), 'success');
  startPolling();
}

/* ============================================================
   EJECUCIÓN — MULTI-MODELO SECUENCIAL (CSV)
   ============================================================ */

/* Espera hasta que el job actual termine (polling cada 3s) */
async function waitForJobDone(generationType) {
  const url = generationType
    ? `${API_BASE}/jobs/current?generation_type=${generationType}`
    : `${API_BASE}/jobs/current`;
  while (true) {
    await new Promise(r => setTimeout(r, 3000));
    try {
      const res = await authFetch(url);
      const job = await res.json();
      if (job.status === 'done' || job.status === 'error' || job.status === 'idle') return job;
    } catch (err) {
      // authFetch ya dispara logout() si la sesion expiro (401). Para
      // cualquier otro error (red, etc.) seguimos esperando como antes.
      if (err.message === 'No autenticado') return { status: 'error' };
    }
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

  // Limpiar las imágenes viejas del servidor antes de empezar, para que
  // fotos de donantes de ejecuciones anteriores no se mezclen con las
  // de esta corrida nueva en la galería.
  try {
    await authFetch(`${API_BASE}/clear_output`, { method: 'POST' });
  } catch (err) {
    console.warn('No se pudo limpiar output_images antes de iniciar:', err.message);
  }

  // Subir CSV al servidor primero
  if (csvFile) {
    const fd = new FormData();
    fd.append('csv', csvFile);
    await authFetch(`${API_BASE}/upload_images`, { method: 'POST', body: fd });
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

  // Filtrar la galeria para mostrar SOLO los donantes de esta corrida,
  // sin borrar nada de Backblaze (el historial completo sigue ahi,
  // simplemente no se muestra mezclado con otros donantes). Ya no hace
  // falta tomar un "snapshot" de lo que existia antes: el propio servidor
  // (list_images_b2) se queda automaticamente solo con la corrida mas
  // reciente por donante+tipo, de forma permanente.
  currentSessionDonors = new Set(queue.map(m => m.vreproID));

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

    const jobRes = await authFetch(`${API_BASE}/jobs?${params}`, { method: 'POST' });
    if (!jobRes.ok) {
      const err = await jobRes.json().catch(() => ({}));
      showToast(`Error iniciando job para ${model.vreproID}: ${err.detail || '?'}`, 'error');
      continue;
    }

    startPolling();
    const jobResult = await waitForJobDone(mode);
    stopPolling();

    if (jobResult.status === 'error') {
      showToast(`Error en job de ${model.vreproID}: ${jobResult.error || '?'}`, 'error');
    }

    // Pausa para asegurar que los archivos están escritos
    await new Promise(r => setTimeout(r, 1000));

    const newImgs = await fetchNewImages();
    modelResults[model.vreproID] = newImgs;
    generatedImgs.push(...newImgs);

    // Evitar duplicados: si el polling automático (que corre en paralelo)
    // ya habia agregado este mismo archivo justo antes, no queremos que
    // aparezca dos veces en la galeria.
    const seen = new Set();
    generatedImgs = generatedImgs.filter(g => {
      if (seen.has(g.filename)) return false;
      seen.add(g.filename);
      return true;
    });

    activeVreproID = null;
    renderModelList();
    renderGen();
    updateApprCount();

    showToast(`✓ ${model.vreproID}: ${newImgs.length} imagen(es) lista(s).`, 'success');

    // Continua automaticamente al siguiente modelo, sin pausa manual.
    updateSeqProgress(i + 1, queue.length, model.vreproID, i === queue.length - 1 ? 'done' : 'processing');
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
   EJECUCIÓN — FULLBODY + PORTRAIT AUTOMÁTICO (uno tras otro)
   ============================================================ */
async function startFullbodyThenPortrait() {
  if (seqRunning) {
    showToast('Ya hay una ejecución en curso.', 'error');
    return;
  }

  const cyclesFb = document.getElementById('fb-cycles').value;
  const cyclesPt = document.getElementById('pt-cycles').value;
  const donors   = document.getElementById('model-list').value;
  const usePose    = document.getElementById('cb-pose').classList.contains('on');
  const useHands   = document.getElementById('cb-hands').classList.contains('on');
  const useAmateur = document.getElementById('cb-amateur').classList.contains('on');

  if (!donors.trim()) {
    showToast('Escribe al menos un vreproID en "LISTA DE MODELOS".', 'error');
    return;
  }

  seqRunning = true;

  try {
    await authFetch(`${API_BASE}/clear_output`, { method: 'POST' });
  } catch (err) {
    console.warn('No se pudo limpiar output_images antes de iniciar:', err.message);
  }

  const runOne = async (mode, cycles) => {
    const params = new URLSearchParams({
      generation_type:    mode,
      max_cycles:         cycles,
      donor_list:         donors,
      use_pose:           usePose,
      use_hands_refiner:  useHands,
      use_amateur_effect: useAmateur,
    });

    const res  = await authFetch(`${API_BASE}/jobs?${params}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    showToast(`Iniciando ${mode}: ${data.job_id.slice(0, 8)}`, 'success');
    const job = await waitForJobDone(mode);
    if (job.status === 'error') {
      showToast(`Error en ${mode}: ${job.error || '?'}`, 'error');
    } else {
      showToast(`✓ ${mode} completado`, 'success');
    }
    await fetchGeneratedImages();
  };

  try {
    await runOne('fullbody', cyclesFb);
    await runOne('portrait', cyclesPt);
    showToast('Fullbody + Portrait completados.', 'success');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  } finally {
    seqRunning = false;
  }
}


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
    await authFetch(`${API_BASE}/interrupt`, { method: 'POST' });
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
  // Al cambiar de modo, la galeria debe mostrar solo las fotos de ese
  // tipo de inmediato, sin esperar al proximo ciclo de polling.
  if (typeof fetchGeneratedImages === 'function') fetchGeneratedImages();
}

function toggleCb(el) {
  el.classList.toggle('on');
}

/* ============================================================
   INIT
   Nota: esta funcion la llama checkExistingSession() desde auth.js,
   una vez confirmada la sesion -- no se dispara sola aqui.
   ============================================================ */
function initApp() {
  checkHealth();
  setInterval(checkHealth, 30000);
  fetchGeneratedImages();
  startPolling();
}
