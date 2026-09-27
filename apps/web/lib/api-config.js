// API configuration for Electron app
const isElectron = typeof window !== 'undefined' && window.electronAPI;

export const API_BASE_URL = isElectron 
  ? 'http://localhost:8000' 
  : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const WS_BASE_URL = isElectron
  ? 'ws://localhost:8000'
  : process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';