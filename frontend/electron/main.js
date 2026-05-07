const { app, BrowserWindow, ipcMain, dialog, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const os = require('os');

let mainWindow;
let backendProcess;
let config = {};

// ─── Config paths ──────────────────────────────────────────────────────────────
const CONFIG_DIR = path.join(app.getPath('userData'), 'config');
const CONFIG_FILE = path.join(CONFIG_DIR, 'settings.json');
const BACKEND_DIR = path.join(__dirname, '..', 'backend');

// ─── Load/Save config ──────────────────────────────────────────────────────────
function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    }
  } catch (e) {
    config = {};
  }
  return config;
}

function saveConfig(newConfig) {
  config = { ...config, ...newConfig };
  try {
    if (!fs.existsSync(CONFIG_DIR)) {
      fs.mkdirSync(CONFIG_DIR, { recursive: true });
    }
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
  } catch (e) {
    console.error('Failed to save config:', e);
  }
  return config;
}

// ─── Find Python ───────────────────────────────────────────────────────────────
function findPython() {
  const candidates = [];
  if (process.platform === 'win32') {
    candidates.push(
      path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe'),
      path.join(BACKEND_DIR, 'python', 'python.exe'),
      'python.exe',
      'python3.exe',
      'py.exe',
    );
  } else {
    candidates.push(
      path.join(BACKEND_DIR, 'venv', 'bin', 'python3'),
      path.join(BACKEND_DIR, 'venv', 'bin', 'python'),
      'python3',
      'python',
    );
  }
  for (const cmd of candidates) {
    try {
      if (cmd.includes(path.sep) && fs.existsSync(cmd)) {
        return cmd;
      }
      // Check if command exists in PATH
      const { execSync } = require('child_process');
      execSync(`${cmd} --version`, { stdio: 'pipe' });
      return cmd;
    } catch (e) {
      continue;
    }
  }
  return null;
}

// ─── Start backend ─────────────────────────────────────────────────────────────
function startBackend() {
  if (backendProcess) {
    console.log('Backend already running');
    return;
  }

  const pythonCmd = findPython();
  if (!pythonCmd) {
    console.error('Python not found!');
    if (mainWindow) {
      mainWindow.webContents.send('backend-error', 'Python not found. Please install Python 3.10+');
    }
    return;
  }

  const mainScript = path.join(BACKEND_DIR, 'main.py');
  if (!fs.existsSync(mainScript)) {
    console.error('Backend main.py not found at:', mainScript);
    if (mainWindow) {
      mainWindow.webContents.send('backend-error', 'Backend files not found.');
    }
    return;
  }

  console.log('Starting backend with:', pythonCmd, mainScript);

  const env = { ...process.env };
  if (config.openrouterApiKey) {
    env.OPENROUTER_API_KEY = config.openrouterApiKey;
  }
  if (config.openrouterModel) {
    env.OPENROUTER_MODEL = config.openrouterModel;
  }

  backendProcess = spawn(pythonCmd, [mainScript], {
    cwd: BACKEND_DIR,
    env,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  backendProcess.stdout.on('data', (data) => {
    const msg = data.toString().trim();
    console.log('[Backend]', msg);
    if (mainWindow) {
      mainWindow.webContents.send('backend-log', msg);
    }
  });

  backendProcess.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    console.error('[Backend ERR]', msg);
    if (mainWindow) {
      mainWindow.webContents.send('backend-error', msg);
    }
  });

  backendProcess.on('close', (code) => {
    console.log('Backend exited with code:', code);
    backendProcess = null;
    if (mainWindow) {
      mainWindow.webContents.send('backend-status', 'stopped');
    }
  });

  backendProcess.on('error', (err) => {
    console.error('Backend process error:', err);
    backendProcess = null;
    if (mainWindow) {
      mainWindow.webContents.send('backend-error', `Failed to start backend: ${err.message}`);
    }
  });

  if (mainWindow) {
    mainWindow.webContents.send('backend-status', 'running');
  }
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

// ─── Get index.html path ───────────────────────────────────────────────────────
function getIndexHtmlPath() {
  if (app.isPackaged) {
    return path.join(__dirname, '..', 'build', 'index.html');
  }
  return path.join(__dirname, '..', 'build', 'index.html');
}

// ─── Create window ─────────────────────────────────────────────────────────────
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  mainWindow = new BrowserWindow({
    width: Math.min(1400, width - 100),
    height: Math.min(900, height - 100),
    minWidth: 1000,
    minHeight: 700,
    backgroundColor: '#0d1117',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  const indexPath = getIndexHtmlPath();
  console.log('Loading:', indexPath);
  mainWindow.loadFile(indexPath).catch(err => {
    console.error('Failed to load:', err);
    mainWindow.loadURL(`data:text/html,<h1 style="color:white;background:#0d1117;padding:40px">Error loading app<br><small>${err.message}</small></h1>`);
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ─── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  loadConfig();
  createWindow();
  // Auto-start backend after a short delay to let the window load
  setTimeout(() => {
    startBackend();
  }, 1000);
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  stopBackend();
});

// ─── IPC handlers ──────────────────────────────────────────────────────────────
ipcMain.handle('get-config', () => {
  return loadConfig();
});

ipcMain.handle('save-config', (event, newConfig) => {
  const updated = saveConfig(newConfig);
  // Restart backend with new config
  stopBackend();
  setTimeout(() => startBackend(), 500);
  return updated;
});

ipcMain.handle('start-backend', () => {
  startBackend();
  return { status: backendProcess ? 'running' : 'stopped' };
});

ipcMain.handle('stop-backend', () => {
  stopBackend();
  return { status: 'stopped' };
});

ipcMain.handle('get-backend-status', () => {
  return { status: backendProcess ? 'running' : 'stopped' };
});

ipcMain.handle('save-file', async (event, { content, filename }) => {
  const { filePath, canceled } = await dialog.showSaveDialog(mainWindow, {
    defaultPath: filename,
    filters: [
      { name: 'All Files', extensions: ['*'] },
      { name: 'MQL5', extensions: ['mq5'] },
      { name: 'HTML', extensions: ['html'] },
    ],
  });
  if (!canceled && filePath) {
    fs.writeFileSync(filePath, content);
    return { success: true, path: filePath };
  }
  return { success: false };
});

ipcMain.handle('export-mt5', async (event, code) => {
  const { filePath, canceled } = await dialog.showSaveDialog(mainWindow, {
    defaultPath: 'Strategy.mq5',
    filters: [{ name: 'MQL5', extensions: ['mq5'] }],
  });
  if (!canceled && filePath) {
    fs.writeFileSync(filePath, code);
    return { success: true, path: filePath };
  }
  return { success: false };
});

ipcMain.handle('check-python', () => {
  const pythonCmd = findPython();
  return { found: !!pythonCmd, path: pythonCmd };
});
