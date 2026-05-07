export {};

declare global {
  interface Window {
    electronAPI: {
      getConfig: () => Promise<any>;
      saveConfig: (config: any) => Promise<any>;
      startBackend: () => Promise<{ status: string }>;
      stopBackend: () => Promise<{ status: string }>;
      getBackendStatus: () => Promise<{ status: string }>;
      checkPython: () => Promise<{ found: boolean; path: string }>;
      saveFile: (content: string, filename: string) => Promise<{ success: boolean; path?: string }>;
      exportMT5: (code: string) => Promise<{ success: boolean; path?: string }>;
      onBackendLog: (callback: (msg: string) => void) => void;
      onBackendError: (callback: (msg: string) => void) => void;
      onBackendStatus: (callback: (status: string) => void) => void;
    };
  }
}
