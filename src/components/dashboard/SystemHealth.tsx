
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { CheckCircle, AlertCircle, XCircle, Activity, Zap, Shield } from 'lucide-react';
import { apiUrl } from '@/config/api';
import { SystemHealth as SystemHealthType, AdvancedMetrics, CircuitBreaker, AgentPerformance } from '@/types/metrics';

export const SystemHealth = () => {
  const { data: healthData, isLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: async (): Promise<SystemHealthType> => {
      const response = await fetch(apiUrl('/api/metrics/health'));
      if (!response.ok) throw new Error('Failed to fetch health data');
      return response.json();
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const { data: advancedMetrics } = useQuery({
    queryKey: ['advanced-metrics'],
    queryFn: async (): Promise<AdvancedMetrics> => {
      const response = await fetch(apiUrl('/api/metrics/advanced'));
      if (!response.ok) throw new Error('Failed to fetch advanced metrics');
      return response.json();
    },
    refetchInterval: 10000,
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'degraded': return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'unhealthy': return <XCircle className="h-4 w-4 text-red-500" />;
      default: return <Activity className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-500';
      case 'degraded': return 'bg-yellow-500'; 
      case 'unhealthy': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>System Health</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-4 bg-gray-200 rounded animate-pulse" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const circuitBreakers = advancedMetrics?.circuit_breakers || {};
  const alerts = healthData?.alerts || [];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {getStatusIcon(healthData?.overall_status)}
            System Health Status
          </CardTitle>
          <CardDescription>Real-time monitoring of AI agent system</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${getStatusColor(healthData?.overall_status)}`} />
              <span className="font-medium capitalize">{healthData?.overall_status || 'Unknown'}</span>
            </div>
            <Badge variant="outline">
              Last updated: {healthData?.timestamp ? new Date(healthData.timestamp).toLocaleTimeString() : 'Unknown'}
            </Badge>
          </div>

          {alerts.length > 0 && (
            <div className="space-y-2 mb-4">
              {alerts.map((alert: string, index: number) => (
                <Alert key={index} variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Alert</AlertTitle>
                  <AlertDescription>{alert}</AlertDescription>
                </Alert>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Circuit Breakers
          </CardTitle>
          <CardDescription>Service protection status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Object.entries(circuitBreakers).map(([service, breaker]: [string, CircuitBreaker]) => (
              <div key={service} className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    breaker.state === 'CLOSED' ? 'bg-green-500' : 
                    breaker.state === 'HALF_OPEN' ? 'bg-yellow-500' : 'bg-red-500'
                  }`} />
                  <span className="font-medium">{service}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={breaker.state === 'CLOSED' ? 'default' : 'destructive'}>
                    {breaker.state}
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    Failures: {breaker.failure_count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Agent Performance Summary
          </CardTitle>
          <CardDescription>Real-time agent execution metrics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Object.entries(advancedMetrics?.agent_performance || {}).map(([agent, metrics]: [string, AgentPerformance]) => (
              <div key={agent} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium capitalize">{agent}</span>
                  <Badge variant="outline">
                    {(metrics.success_rate * 100).toFixed(1)}% success
                  </Badge>
                </div>
                <Progress value={metrics.success_rate * 100} className="h-2" />
                <div className="flex justify-between text-sm text-muted-foreground">
                  <span>Avg: {metrics.avg_duration?.toFixed(2)}s</span>
                  <span>Total: {metrics.total_executions}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
