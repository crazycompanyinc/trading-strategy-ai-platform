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
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0d1117',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    icon: path.join(__dirname, '../public/icon.png'),
  });

  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    const indexPath = path.join(__dirname, '../build/index.html');
    mainWindow.loadFile(indexPath);
  }

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// IPC handlers
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
