const { app, BrowserWindow, ipcMain, dialog, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

let mainWindow;
let backendProcess;
let config = {};
let backendTempDir = null;
let depsInstalled = false;

// ─── Config ────────────────────────────────────────────────────────────────────
const CONFIG_DIR = path.join(app.getPath('userData'), 'config');
const CONFIG_FILE = path.join(CONFIG_DIR, 'settings.json');

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    }
  } catch (e) { config = {}; }
  return config;
}

function saveConfig(newConfig) {
  config = { ...config, ...newConfig };
  try {
    if (!fs.existsSync(CONFIG_DIR)) fs.mkdirSync(CONFIG_DIR, { recursive: true });
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
  } catch (e) { console.error('saveConfig:', e); }
  return config;
}

// ─── Extract backend from asar ─────────────────────────────────────────────────
function extractBackend() {
  if (backendTempDir && fs.existsSync(path.join(backendTempDir, 'main.py'))) {
    return backendTempDir;
  }
  backendTempDir = path.join(os.tmpdir(), 'trading-strategy-backend');
  try {
    if (!fs.existsSync(backendTempDir)) fs.mkdirSync(backendTempDir, { recursive: true });

    const asarRoot = path.dirname(__dirname);
    const appRoot = path.dirname(asarRoot);
    const locations = [
      path.join(appRoot, 'backend'),
      path.join(asarRoot, 'backend'),
      path.join(path.dirname(app.getPath('exe')), 'backend'),
    ];
    let src = null;
    for (const loc of locations) {
      if (fs.existsSync(path.join(loc, 'main.py'))) { src = loc; break; }
    }
    if (!src) {
      console.error('Backend not found in any location:', locations);
      if (mainWindow) mainWindow.webContents.send('backend-error', 'Backend files not found.');
      return null;
    }
    console.log('Copying backend from:', src);
    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (const entry of entries) {
      const s = path.join(src, entry.name);
      const d = path.join(backendTempDir, entry.name);
      if (entry.isDirectory()) { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); copyDir(s, d); }
      else { fs.copyFileSync(s, d); }
    }
    console.log('Backend extracted to:', backendTempDir);
    return backendTempDir;
  } catch (e) {
    console.error('extractBackend:', e);
    return null;
  }
}

function copyDir(src, dest) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); copyDir(s, d); }
    else { fs.copyFileSync(s, d); }
  }
}

// ─── Find Python ───────────────────────────────────────────────────────────────
function findPython() {
  const backendDir = extractBackend();
  const cands = process.platform === 'win32'
    ? [path.join(backendDir||'','venv','Scripts','python.exe'), path.join(process.resourcesPath,'python','python.exe'), 'python.exe', 'python3.exe', 'py.exe']
    : [path.join(backendDir||'','venv','bin','python3'), 'python3', 'python'];
  for (const cmd of cands) {
    if (!cmd) continue;
    try {
      if (cmd.includes(path.sep) && fs.existsSync(cmd)) return cmd;
      const { execSync } = require('child_process');
      execSync(`"${cmd}" --version`, { stdio: 'pipe' });
      return cmd;
    } catch(e) {}
  }
  return null;
}

// ─── Install deps ──────────────────────────────────────────────────────────────
function installDeps(backendDir, pythonCmd) {
  return new Promise((resolve, reject) => {
    const req = path.join(backendDir, 'requirements.txt');
    if (!fs.existsSync(req)) { resolve(); return; }
    console.log('pip install -r', req);
    if (mainWindow) mainWindow.webContents.send('backend-log', 'Installing Python dependencies (first run, may take a minute)...');
    const p = spawn(pythonCmd, ['-m','pip','install','-r', req], { cwd: backendDir, windowsHide: true, timeout: 180000 });
    p.stdout.on('data', d => { if (mainWindow) mainWindow.webContents.send('backend-log', d.toString().trim()); });
    p.stderr.on('data', d => { if (mainWindow) mainWindow.webContents.send('backend-log', d.toString().trim()); });
    p.on('close', code => {
      if (code === 0) {
        console.log('pip install OK');
        if (mainWindow) mainWindow.webContents.send('backend-log', '✓ Dependencies installed successfully');
        depsInstalled = true;
        resolve();
      } else {
        const m = `pip install failed (exit ${code}). Install manually: pip install -r requirements.txt`;
        if (mainWindow) mainWindow.webContents.send('backend-error', m);
        reject(new Error(m));
      }
    });
    p.on('error', reject);
  });
}

// ─── Start backend ─────────────────────────────────────────────────────────────
async function startBackend() {
  if (backendProcess) return;

  const backendDir = extractBackend();
  if (!backendDir) return;

  const pythonCmd = findPython();
  if (!pythonCmd) {
    if (mainWindow) mainWindow.webContents.send('backend-error', 'Python not found. Install Python 3.10+ and restart.');
    return;
  }

  // Install deps if not done yet
  if (!depsInstalled) {
    try { await installDeps(backendDir, pythonCmd); } catch(e) { console.warn('pip install failed, continuing anyway'); }
  }

  const mainScript = path.join(backendDir, 'main.py');
  console.log('Starting backend:', pythonCmd, mainScript);

  const env = { ...process.env };
  if (config.openrouterApiKey) env.OPENROUTER_API_KEY = config.openrouterApiKey;
  if (config.openrouterModel) env.OPENROUTER_MODEL = config.openrouterModel;

  try {
    backendProcess = spawn(pythonCmd, [mainScript], { cwd: backendDir, env, stdio: ['pipe','pipe','pipe'], windowsHide: true });
    backendProcess.stdout.on('data', d => { const m = d.toString().trim(); console.log('[B]', m); if (mainWindow) mainWindow.webContents.send('backend-log', m); });
    backendProcess.stderr.on('data', d => { const m = d.toString().trim(); console.error('[BE]', m); if (mainWindow) mainWindow.webContents.send('backend-error', m); });
    backendProcess.on('close', code => { console.log('Backend exited:', code); backendProcess = null; if (mainWindow) mainWindow.webContents.send('backend-status', 'stopped'); });
    backendProcess.on('error', err => { console.error('Backend error:', err); backendProcess = null; if (mainWindow) mainWindow.webContents.send('backend-error', `Start failed: ${err.message}`); });
    if (mainWindow) mainWindow.webContents.send('backend-status', 'running');
  } catch (err) {
    if (mainWindow) mainWindow.webContents.send('backend-error', `Spawn failed: ${err.message}`);
  }
}

function stopBackend() {
  if (backendProcess) { try { backendProcess.kill(); } catch(e) {} backendProcess = null; }
}

// ─── Window ────────────────────────────────────────────────────────────────────
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  mainWindow = new BrowserWindow({
    width: Math.min(1400, width - 100), height: Math.min(900, height - 100),
    minWidth: 1000, minHeight: 700, backgroundColor: '#0d1117',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false, sandbox: false,
    },
  });
  const idx = path.join(__dirname, '..', 'build', 'index.html');
  mainWindow.loadFile(idx).catch(e => mainWindow.loadURL(`data:text/html,<h1 style="color:white;background:#0d1117;padding:40px">Error: ${e.message}</h1>`));
  mainWindow.on('closed', () => { mainWindow = null; });
}

// ─── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(() => { loadConfig(); createWindow(); setTimeout(() => startBackend(), 1500); });
app.on('window-all-closed', () => { stopBackend(); if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
app.on('before-quit', () => stopBackend());

// ─── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.handle('get-config', () => loadConfig());
ipcMain.handle('save-config', (e, nc) => { const u = saveConfig(nc); stopBackend(); setTimeout(() => startBackend(), 500); return u; });
ipcMain.handle('start-backend', () => { startBackend(); return { status: backendProcess ? 'running' : 'stopped' }; });
ipcMain.handle('stop-backend', () => { stopBackend(); return { status: 'stopped' }; });
ipcMain.handle('get-backend-status', () => ({ status: backendProcess ? 'running' : 'stopped' }));
ipcMain.handle('check-python', () => { const p = findPython(); return { found: !!p, path: p }; });
ipcMain.handle('save-file', async (e, {content, filename}) => {
  const {filePath, canceled} = await dialog.showSaveDialog(mainWindow, { defaultPath: filename, filters: [{name:'All',extensions:['*']},{name:'MQL5',extensions:['mq5']}] });
  if (!canceled && filePath) { fs.writeFileSync(filePath, content); return {success:true, path:filePath}; }
  return {success:false};
});
ipcMain.handle('export-mt5', async (e, code) => {
  const {filePath, canceled} = await dialog.showSaveDialog(mainWindow, { defaultPath: 'Strategy.mq5', filters: [{name:'MQL5',extensions:['mq5']}] });
  if (!canceled && filePath) { fs.writeFileSync(filePath, code); return {success:true, path:filePath}; }
  return {success:false};
});
