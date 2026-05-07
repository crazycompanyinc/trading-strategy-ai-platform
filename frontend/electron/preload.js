const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Config
  getConfig: () => ipcRenderer.invoke('get-config'),
  saveConfig: (config) => ipcRenderer.invoke('save-config', config),

  // Backend control
  startBackend: () => ipcRenderer.invoke('start-backend'),
  stopBackend: () => ipcRenderer.invoke('stop-backend'),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  checkPython: () => ipcRenderer.invoke('check-python'),

  // File operations
  saveFile: (content, filename) => ipcRenderer.invoke('save-file', { content, filename }),
  exportMT5: (code) => ipcRenderer.invoke('export-mt5', code),

  // Event listeners
  onBackendLog: (callback) => ipcRenderer.on('backend-log', (event, msg) => callback(msg)),
  onBackendError: (callback) => ipcRenderer.on('backend-error', (event, msg) => callback(msg)),
  onBackendStatus: (callback) => ipcRenderer.on('backend-status', (event, status) => callback(status)),
});
