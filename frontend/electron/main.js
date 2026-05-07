const { app, BrowserWindow, ipcMain, dialog, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

let mainWindow;
let backendProcess;
let config = {};
let backendTempDir = null;

// ─── Config paths ──────────────────────────────────────────────────────────────
const CONFIG_DIR = path.join(app.getPath('userData'), 'config');
const CONFIG_FILE = path.join(CONFIG_DIR, 'settings.json');

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

// ─── Extract backend from asar to temp dir ─────────────────────────────────────
function extractBackend() {
  if (backendTempDir && fs.existsSync(path.join(backendTempDir, 'main.py'))) {
    return backendTempDir;
  }

  // Create temp directory for backend
  backendTempDir = path.join(os.tmpdir(), 'trading-strategy-backend');
  
  try {
    if (!fs.existsSync(backendTempDir)) {
      fs.mkdirSync(backendTempDir, { recursive: true });
    }

    // Source: backend is bundled inside asar at electron/../backend
    // When packaged, __dirname is something like:
    // C:\Users\...\AppData\Local\Programs\trading-strategy\resources\app.asar\electron
    // The backend folder is at: resources/app.asar/../backend = resources/backend
    // But since we're inside asar, we need to go to the asar root first
    
    const asarRoot = path.dirname(__dirname); // resources/app.asar
    const appRoot = path.dirname(asarRoot);   // resources/
    const backendSrc = path.join(appRoot, 'backend');

    console.log('__dirname:', __dirname);
    console.log('asarRoot:', asarRoot);
    console.log('appRoot:', appRoot);
    console.log('backendSrc:', backendSrc);
    console.log('backendSrc exists:', fs.existsSync(backendSrc));

    if (fs.existsSync(backendSrc)) {
      // Backend is outside asar (portable extraction)
      console.log('Backend found outside asar, copying...');
      copyDirSync(backendSrc, backendTempDir);
    } else {
      // Backend might be inside asar as extraResources
      // Try: resources/backend (electron-builder extraResources)
      const extraBackend = path.join(asarRoot, 'backend');
      console.log('extraBackend:', extraBackend);
      console.log('extraBackend exists:', fs.existsSync(extraBackend));
      
      if (fs.existsSync(extraBackend)) {
        console.log('Backend found as extraResources, copying...');
        copyDirSync(extraBackend, backendTempDir);
      } else {
        // Last resort: check if backend is at the same level as the .exe
        const exeDir = path.dirname(app.getPath('exe'));
        const exeBackend = path.join(exeDir, 'backend');
        console.log('exeBackend:', exeBackend);
        console.log('exeBackend exists:', fs.existsSync(exeBackend));
        
        if (fs.existsSync(exeBackend)) {
          console.log('Backend found next to exe, copying...');
          copyDirSync(exeBackend, backendTempDir);
        } else {
          console.error('Backend not found anywhere!');
          return null;
        }
      }
    }

    console.log('Backend extracted to:', backendTempDir);
    console.log('main.py exists:', fs.existsSync(path.join(backendTempDir, 'main.py')));
    return backendTempDir;
  } catch (e) {
    console.error('Failed to extract backend:', e);
    return null;
  }
}

function copyDirSync(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

// ─── Find Python ───────────────────────────────────────────────────────────────
function findPython() {
  const backendDir = extractBackend();
  
  const candidates = [];
  if (process.platform === 'win32') {
    candidates.push(
      path.join(backendDir || '', 'venv', 'Scripts', 'python.exe'),
      path.join(backendDir || '', 'python', 'python.exe'),
      path.join(process.resourcesPath, 'python', 'python.exe'),
      'python.exe',
      'python3.exe',
      'py.exe',
    );
  } else {
    candidates.push(
      path.join(backendDir || '', 'venv', 'bin', 'python3'),
      path.join(backendDir || '', 'venv', 'bin', 'python'),
      'python3',
      'python',
    );
  }
  
  for (const cmd of candidates) {
    if (!cmd) continue;
    try {
      if (cmd.includes(path.sep) && fs.existsSync(cmd)) {
        return cmd;
      }
      // Check PATH
      const { execSync } = require('child_process');
      execSync(`"${cmd}" --version`, { stdio: 'pipe' });
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

  const backendDir = extractBackend();
  if (!backendDir) {
    const msg = 'Could not find backend files. The app may need to be reinstalled.';
    console.error(msg);
    if (mainWindow) mainWindow.webContents.send('backend-error', msg);
    return;
  }

  const pythonCmd = findPython();
  if (!pythonCmd) {
    const msg = 'Python not found. Please install Python 3.10+ from python.org';
    console.error(msg);
    if (mainWindow) mainWindow.webContents.send('backend-error', msg);
    return;
  }

  const mainScript = path.join(backendDir, 'main.py');
  if (!fs.existsSync(mainScript)) {
    const msg = `Backend main.py not found at: ${mainScript}`;
    console.error(msg);
    if (mainWindow) mainWindow.webContents.send('backend-error', msg);
    return;
  }

  console.log('Starting backend:');
  console.log('  Python:', pythonCmd);
  console.log('  Script:', mainScript);
  console.log('  CWD:', backendDir);

  const env = { ...process.env };
  if (config.openrouterApiKey) {
    env.OPENROUTER_API_KEY = config.openrouterApiKey;
  }
  if (config.openrouterModel) {
    env.OPENROUTER_MODEL = config.openrouterModel;
  }

  try {
    backendProcess = spawn(pythonCmd, [mainScript], {
      cwd: backendDir,
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true, // Don't show console window on Windows
    });

    backendProcess.stdout.on('data', (data) => {
      const msg = data.toString().trim();
      console.log('[Backend]', msg);
      if (mainWindow) mainWindow.webContents.send('backend-log', msg);
    });

    backendProcess.stderr.on('data', (data) => {
      const msg = data.toString().trim();
      console.error('[Backend ERR]', msg);
      if (mainWindow) mainWindow.webContents.send('backend-error', msg);
    });

    backendProcess.on('close', (code) => {
      console.log('Backend exited with code:', code);
      backendProcess = null;
      if (mainWindow) mainWindow.webContents.send('backend-status', 'stopped');
    });

    backendProcess.on('error', (err) => {
      console.error('Backend process error:', err);
      backendProcess = null;
      if (mainWindow) mainWindow.webContents.send('backend-error', `Failed to start: ${err.message}`);
    });

    if (mainWindow) mainWindow.webContents.send('backend-status', 'running');
  } catch (err) {
    console.error('Failed to spawn backend:', err);
    if (mainWindow) mainWindow.webContents.send('backend-error', `Failed to start backend: ${err.message}`);
  }
}

function stopBackend() {
  if (backendProcess) {
    try {
      backendProcess.kill();
    } catch (e) {}
    backendProcess = null;
  }
}

// ─── Get index.html path ───────────────────────────────────────────────────────
function getIndexHtmlPath() {
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
  setTimeout(() => startBackend(), 1500);
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on('before-quit', () => stopBackend());

// ─── IPC handlers ──────────────────────────────────────────────────────────────
ipcMain.handle('get-config', () => loadConfig());
ipcMain.handle('save-config', (event, newConfig) => {
  const updated = saveConfig(newConfig);
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
