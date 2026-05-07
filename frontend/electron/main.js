const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
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

  // Load the React app
  // In dev: electron/ is at project root, build/ is sibling
  // In production: both are inside asar at same level
  let indexPath;
  if (app.isPackaged) {
    // Inside asar: electron/main.js -> ../build/index.html
    indexPath = path.join(__dirname, '..', 'build', 'index.html');
  } else {
    // Development: electron/ is in project root
    indexPath = path.join(__dirname, '..', 'build', 'index.html');
  }

  console.log('Loading index from:', indexPath);
  console.log('__dirname:', __dirname);
  console.log('isPackaged:', app.isPackaged);
  console.log('appPath:', app.getAppPath());

  mainWindow.loadFile(indexPath).catch(err => {
    console.error('Failed to load index.html:', err.message);
    // Fallback: try loading from app path
    const fallback = path.join(app.getAppPath(), 'build', 'index.html');
    console.log('Trying fallback:', fallback);
    mainWindow.loadFile(fallback).catch(e => {
      console.error('Fallback also failed:', e.message);
      // Last resort: load a simple error page
      mainWindow.loadURL('data:text/html,<h1>Error loading app</h1><p>' + e.message + '</p>');
    });
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
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
