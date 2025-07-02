// Mock API service for development when backend is not available
import { SystemMetrics } from '@/types/metrics';

export const mockSystemMetrics: SystemMetrics = {
  total_tickets: 47,
  active_tickets: 8,
  success_rate: 94.5,
  completed_tickets: 39,
  avg_resolution_time: 12.3
};

export const mockTickets = [
  {
    id: "1",
    title: "Login authentication issue",
    jira_id: "JIRA-123",
    status: "in_progress",
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
  },
  {
    id: "2", 
    title: "Database connection timeout",
    jira_id: "JIRA-124",
    status: "completed",
    created_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString()
  },
  {
    id: "3",
    title: "UI component styling bug", 
    jira_id: "JIRA-125",
    status: "pending",
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString()
  }
];

export const mockAgentStatus = [
  { id: 'developer', name: 'Developer Agent', status: 'active', tasksCompleted: 12, currentTask: 'Analyzing code patterns' },
  { id: 'qa', name: 'QA Agent', status: 'active', tasksCompleted: 8, currentTask: 'Running test suite' },
  { id: 'planner', name: 'Planner Agent', status: 'idle', tasksCompleted: 5, currentTask: null }
];

export const mockHealthData = {
  overall_status: 'healthy' as const,
  timestamp: new Date().toISOString(),
  alerts: ['High memory usage detected']
};

export const mockLogs = [
  {
    id: 1,
    timestamp: new Date().toISOString(),
    level: 'info',
    message: 'Agent successfully processed ticket #123',
    source: 'developer-agent'
  },
  {
    id: 2,
    timestamp: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    level: 'warning',
    message: 'High memory usage detected (85%)',
    source: 'system-monitor'
  },
  {
    id: 3,
    timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    level: 'error',
    message: 'Failed to connect to external service',
    source: 'api-gateway'
  }
];

// Mock API functions
export const mockApi = {
  getSystemMetrics: () => Promise.resolve(mockSystemMetrics),
  getTickets: () => Promise.resolve(mockTickets),
  getAgentStatus: () => Promise.resolve(mockAgentStatus),
  getHealthData: () => Promise.resolve(mockHealthData),
  getLogs: () => Promise.resolve(mockLogs),
  toggleAgent: (agentType: string) => Promise.resolve({ success: true }),
  retryTicket: (ticketId: number) => Promise.resolve({ success: true }),
  escalateTicket: (ticketId: number) => Promise.resolve({ success: true })
};