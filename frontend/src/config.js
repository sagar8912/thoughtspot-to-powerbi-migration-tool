// Application configuration for ThoughtSpot -> Power BI Migration Tool

export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  wsBaseUrl: import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000',

  apiPrefix: '/api/v1',

  maxFileSize: 100 * 1024 * 1024, // 100MB
  maxFiles: 10,

  allowedExtensions: [
    '.tml',
    '.yaml',
    '.yml',
    '.json',
    '.zip',
    '.csv',
    '.xlsx',
    '.xls',
  ],

  pollInterval: 3000, // 3 seconds
  uploadTimeout: 300000, // 5 minutes

  appName: 'ThoughtSpot to Power BI Migration',
};