
// API configuration - Using mock data when backend is not available
export const API_CONFIG = {
  baseUrl: import.meta.env.REACT_APP_API_URL || 'http://localhost:8000',
  wsUrl: import.meta.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws',
  useMockData: true, // Set to false when backend is available
};

export const apiUrl = (path: string) => `${API_CONFIG.baseUrl}${path}`;

// Check if backend is available
export const isBackendAvailable = async (): Promise<boolean> => {
  try {
    const response = await fetch(`${API_CONFIG.baseUrl}/health`, { 
      method: 'GET',
      signal: AbortSignal.timeout(2000) 
    });
    return response.ok;
  } catch {
    return false;
  }
};
