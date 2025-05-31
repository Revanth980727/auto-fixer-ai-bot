
export interface SystemMetrics {
  total_tickets: number;
  active_tickets: number;
  success_rate: number;
  completed_tickets: number;
  avg_resolution_time: number;
}

export interface Ticket {
  id: string;
  title: string;
  jira_id: string;
  status: string;
  created_at: string;
}

export interface SystemHealth {
  overall_status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  alerts: string[];
}

export interface CircuitBreaker {
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  failure_count: number;
}

export interface AgentPerformance {
  success_rate: number;
  avg_duration: number;
  total_executions: number;
}

export interface Pipeline {
  context_id: string;
  ticket_id: string;
  current_stage: string;
  has_errors: boolean;
  total_duration?: number;
  stages_completed: number;
  checkpoints?: string[];
}

export interface AdvancedMetrics {
  pipeline_summary: Pipeline[];
  circuit_breakers: Record<string, CircuitBreaker>;
  agent_performance: Record<string, AgentPerformance>;
}

export interface MetricsChartsData {
  successRate: Array<{
    date: string;
    rate: number;
  }>;
  agentActivity: Array<{
    agent: string;
    tasks: number;
    success_rate: number;
    avg_duration: number;
  }>;
  errorTypes: Array<{
    name: string;
    value: number;
    color: string;
  }>;
}

export interface PerformanceTrends {
  [metric: string]: {
    avg_value: number;
    trend_direction: 'increasing' | 'decreasing' | 'stable';
    data_points: number;
  };
}
