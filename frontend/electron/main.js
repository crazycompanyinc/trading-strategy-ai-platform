const { app, BrowserWindow, ipcMain, dialog, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');

let mainWindow;
let backendProcess;
let config = {};
let backendTempDir = null;
let depsInstalled = false;

// ─── Config ────────────────────────────────────────────────────────────────────
const CONFIG_DIR = path.join(app.getPath('userData'), 'config');
const CONFIG_FILE = path.join(CONFIG_DIR, 'settings.json');

function loadConfig() {
  try { if (fs.existsSync(CONFIG_FILE)) config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8')); }
  catch(e) { config = {}; }
  return config;
}
function saveConfig(nc) {
  config = { ...config, ...nc };
  try { if (!fs.existsSync(CONFIG_DIR)) fs.mkdirSync(CONFIG_DIR, { recursive: true }); fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2)); }
  catch(e) { console.error('saveConfig:', e); }
  return config;
}

// ─── Log helper ────────────────────────────────────────────────────────────────
function log(msg) { console.log('[Launcher]', msg); if (mainWindow) mainWindow.webContents.send('backend-log', msg); }
function logErr(msg) { console.error('[Launcher]', msg); if (mainWindow) mainWindow.webContents.send('backend-error', msg); }

// ─── Extract backend ───────────────────────────────────────────────────────────
function extractBackend() {
  if (backendTempDir && fs.existsSync(path.join(backendTempDir, 'main.py'))) return backendTempDir;
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
    if (!src) { logErr('Backend not found in: ' + locations.join(', ')); return null; }
    log('Copying backend from: ' + src);
    for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
      const s = path.join(src, entry.name), d = path.join(backendTempDir, entry.name);
      if (entry.isDirectory()) { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); copyDir(s, d); }
      else fs.copyFileSync(s, d);
    }
    log('Backend extracted to: ' + backendTempDir);
    return backendTempDir;
  } catch(e) { logErr('extractBackend: ' + e.message); return null; }
}

function copyDir(src, dest) {
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name), d = path.join(dest, entry.name);
    if (entry.isDirectory()) { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); copyDir(s, d); }
    else fs.copyFileSync(s, d);
  }
}

// ─── Find Python ───────────────────────────────────────────────────────────────
function findPython() {
  log('Searching for Python...');
  const backendDir = extractBackend();
  const isWin = process.platform === 'win32';
  
  // Build candidate list
  const cands = [];
  if (isWin) {
    cands.push(
      path.join(backendDir||'','venv','Scripts','python.exe'),
      path.join(process.resourcesPath||'','python','python.exe'),
      'py.exe', 'python.exe', 'python3.exe',
    );
    // Check common install locations
    const localAppData = process.env.LOCALAPPDATA || '';
    const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
    const programFilesX86 = process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)';
    cands.push(
      path.join(localAppData,'Programs','Python','Python312','python.exe'),
      path.join(localAppData,'Programs','Python','Python311','python.exe'),
      path.join(localAppData,'Programs','Python','Python310','python.exe'),
      path.join(programFiles,'Python312','python.exe'),
      path.join(programFiles,'Python311','python.exe'),
      path.join(programFiles,'Python310','python.exe'),
      path.join(programFilesX86,'Python312','python.exe'),
      path.join(programFilesX86,'Python311','python.exe'),
    );
  } else {
    cands.push(
      path.join(backendDir||'','venv','bin','python3'),
      'python3', 'python',
    );
  }

  for (const cmd of cands) {
    if (!cmd) continue;
    try {
      if (cmd.includes(path.sep)) {
        if (fs.existsSync(cmd)) { log('Found Python at: ' + cmd); return cmd; }
      } else {
        const out = execSync(`"${cmd}" --version`, { stdio: 'pipe', timeout: 5000 }).toString().trim();
        log('Found Python in PATH: ' + cmd + ' -> ' + out);
        return cmd;
      }
    } catch(e) {}
  }
  logErr('Python not found. Tried: ' + cands.length + ' locations');
  return null;
}

// ─── Install deps ──────────────────────────────────────────────────────────────
function runCmd(cmd, args, opts) {
  return new Promise((resolve, reject) => {
    log(`Running: ${cmd} ${args.join(' ')}`);
    const p = spawn(cmd, args, { windowsHide: true, timeout: 600000, ...opts });
    let out = '', err = '';
    p.stdout.on('data', d => { out += d.toString(); log(d.toString().trim()); });
    p.stderr.on('data', d => { err += d.toString(); log(d.toString().trim()); });
    p.on('close', code => {
      if (code === 0) resolve(out);
      else reject(new Error(`exit ${code}: ${(err||out).slice(-200)}`));
    });
    p.on('error', reject);
  });
}

async function installDeps(backendDir, pythonCmd) {
  const req = path.join(backendDir, 'requirements.txt');
  if (!fs.existsSync(req)) { log('No requirements.txt, skipping'); return true; }

  log('Installing Python dependencies (this may take a few minutes on first run)...');

  // Ensure pip
  try {
    await runCmd(pythonCmd, ['-m', 'pip', '--version'], { timeout: 15000 });
  } catch(e) {
    log('pip not found, running ensurepip...');
    try { await runCmd(pythonCmd, ['-m', 'ensurepip', '--upgrade'], { timeout: 30000 }); }
    catch(e2) { logErr('ensurepip failed: ' + e2.message); }
  }

  // Install - use --prefer-binary to avoid compiling from source
  await runCmd(pythonCmd, ['-m', 'pip', 'install', '--prefer-binary', '-r', req], { cwd: backendDir });
  log('✓ Dependencies installed successfully');
  depsInstalled = true;
  return true;
}

// ─── Start backend ─────────────────────────────────────────────────────────────
async function startBackend() {
  if (backendProcess) { log('Backend already running'); return; }

  const backendDir = extractBackend();
  if (!backendDir) { logErr('Cannot find backend files'); return; }

  const pythonCmd = findPython();
  if (!pythonCmd) {
    logErr('Python NOT FOUND. Install Python 3.10+ from https://python.org and restart.');
    return;
  }

  // Install deps first - BLOCKING, don't start backend until done
  if (!depsInstalled) {
    try {
      await installDeps(backendDir, pythonCmd);
    } catch(e) {
      logErr('pip install FAILED: ' + e.message);
      logErr('Backend will not start. Install deps manually: py -m pip install -r requirements.txt');
      return; // DON'T start backend if deps failed
    }
  }

  const mainScript = path.join(backendDir, 'main.py');
  if (!fs.existsSync(mainScript)) { logErr('main.py not found: ' + mainScript); return; }

  log('Starting backend: ' + pythonCmd + ' ' + mainScript);

  const env = { ...process.env };
  if (config.openrouterApiKey) env.OPENROUTER_API_KEY = config.openrouterApiKey;
  if (config.openrouterModel) env.OPENROUTER_MODEL = config.openrouterModel;

  try {
    backendProcess = spawn(pythonCmd, [mainScript], { cwd: backendDir, env, stdio: ['pipe','pipe','pipe'], windowsHide: true });
    backendProcess.stdout.on('data', d => { const m = d.toString().trim(); console.log('[B]', m); if (mainWindow) mainWindow.webContents.send('backend-log', m); });
    backendProcess.stderr.on('data', d => { const m = d.toString().trim(); console.error('[BE]', m); if (mainWindow) mainWindow.webContents.send('backend-error', m); });
    backendProcess.on('close', code => { log('Backend exited: ' + code); backendProcess = null; if (mainWindow) mainWindow.webContents.send('backend-status', 'stopped'); });
    backendProcess.on('error', err => { logErr('Backend error: ' + err.message); backendProcess = null; });
    if (mainWindow) mainWindow.webContents.send('backend-status', 'running');
  } catch(err) {
    logErr('Spawn failed: ' + err.message);
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
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: false },
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
