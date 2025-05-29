
// API configuration
export const API_CONFIG = {
  baseUrl: import.meta.env.REACT_APP_API_URL || 'http://localhost:8000',
  wsUrl: import.meta.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws',
};

export const apiUrl = (path: string) => `${API_CONFIG.baseUrl}${path}`;
