/* ============================================================
   BatchApp Frontend — auth.js
   Modulo separado de autenticacion. Debe cargarse ANTES de app.js
   en index.html, ya que define API_BASE, authFetch, y dispara
   checkExistingSession() -> initApp() (definida en app.js) al final.
   ============================================================ */

const API_BASE = window.API_BASE || 'https://batchapp-frontend.onrender.com';

let sessionToken = localStorage.getItem('batchapp_token') || null;
let userRole = localStorage.getItem('batchapp_role') || null;

/**
 * Wrapper de fetch que agrega automaticamente la cabecera de
 * autenticacion a todas las peticiones al backend. Si el servidor
 * responde 401 (sesion invalida o expirada), fuerza el logout.
 */
async function authFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (sessionToken) headers['Authorization'] = `Bearer ${sessionToken}`;
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    logout('Tu sesión expiró. Inicia sesión de nuevo.');
    throw new Error('No autenticado');
  }
  return res;
}

function showLoginScreen(errorMsg) {
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('main-app').style.display = 'none';
  const errEl = document.getElementById('login-error');
  if (errEl) errEl.textContent = errorMsg || '';
}

function showMainApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('main-app').style.display = 'flex';
  const adminBtn = document.getElementById('admin-panel-link');
  if (adminBtn) adminBtn.style.display = (userRole === 'admin') ? 'inline-block' : 'none';
}

function logout(message) {
  sessionToken = null;
  userRole = null;
  localStorage.removeItem('batchapp_token');
  localStorage.removeItem('batchapp_role');
  if (typeof stopPolling === 'function') stopPolling();
  showLoginScreen(message || '');
}

async function checkExistingSession() {
  if (!sessionToken) {
    showLoginScreen();
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/session_check`, {
      headers: { 'Authorization': `Bearer ${sessionToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      userRole = data.role || 'user';
      localStorage.setItem('batchapp_role', userRole);
      showMainApp();
      initApp();
    } else {
      logout();
    }
  } catch {
    // Si el servidor no responde, no cerramos sesion de golpe -- dejamos
    // que el usuario reintente en vez de perder la sesion por un problema
    // temporal de red.
    showLoginScreen('No se pudo verificar la sesión. Revisa tu conexión e intenta de nuevo.');
  }
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl    = document.getElementById('login-error');
  const btn      = document.getElementById('login-submit');

  errEl.textContent = '';
  btn.disabled = true;
  btn.textContent = 'Entrando...';

  try {
    const res = await fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Usuario o contraseña incorrectos');

    sessionToken = data.token;
    userRole = data.role || 'user';
    localStorage.setItem('batchapp_token', sessionToken);
    localStorage.setItem('batchapp_role', userRole);
    showMainApp();
    initApp();
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Entrar';
  }
});

/* Dispara la verificacion de sesion al cargar la pagina.
   Si hay un token guardado y valido, entra directo a la app
   (initApp(), definida en app.js) sin pedir login de nuevo. */
checkExistingSession();
