const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  saveFile: (content, filename) => ipcRenderer.invoke('save-file', { content, filename }),
  exportMT5: (code) => ipcRenderer.invoke('export-mt5', code),
});
