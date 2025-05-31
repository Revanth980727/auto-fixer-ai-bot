
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TicketTable } from '@/components/dashboard/TicketTable';
import { AgentStatus } from '@/components/dashboard/AgentStatus';
import { MetricsCharts } from '@/components/dashboard/MetricsCharts';
import { LiveLogs } from '@/components/dashboard/LiveLogs';
import { SystemHealth } from '@/components/dashboard/SystemHealth';
import { PipelineMonitor } from '@/components/dashboard/PipelineMonitor';
import { WebSocketProvider } from '@/components/providers/WebSocketProvider';
import { Activity, AlertCircle, CheckCircle, Clock, TrendingUp, Shield } from 'lucide-react';
import { apiUrl } from '@/config/api';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('overview');

  // Fetch system metrics
  const { data: systemMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: async () => {
      const response = await fetch(apiUrl('/api/metrics/system'));
      if (!response.ok) throw new Error('Failed to fetch metrics');
      return response.json();
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Fetch recent tickets
  const { data: tickets, isLoading: ticketsLoading } = useQuery({
    queryKey: ['tickets'],
    queryFn: async () => {
      const response = await fetch(apiUrl('/api/tickets?limit=20'));
      if (!response.ok) throw new Error('Failed to fetch tickets');
      return response.json();
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Fetch system health
  const { data: systemHealth } = useQuery({
    queryKey: ['system-health'],
    queryFn: async () => {
      const response = await fetch(apiUrl('/api/metrics/health'));
      if (!response.ok) throw new Error('Failed to fetch health data');
      return response.json();
    },
    refetchInterval: 5000,
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      case 'in_progress': return 'bg-blue-500';
      case 'escalated': return 'bg-orange-500';
      default: return 'bg-gray-500';
    }
  };

  const getHealthBadge = () => {
    const status = systemHealth?.overall_status || 'unknown';
    const variant = status === 'healthy' ? 'default' : status === 'degraded' ? 'secondary' : 'destructive';
    const icon = status === 'healthy' ? <CheckCircle className="w-4 h-4 mr-1" /> : 
                 status === 'degraded' ? <AlertCircle className="w-4 h-4 mr-1" /> : 
                 <Shield className="w-4 h-4 mr-1" />;
    
    return (
      <Badge variant={variant as any}>
        {icon}
        System {status}
      </Badge>
    );
  };

  return (
    <WebSocketProvider>
      <div className="min-h-screen bg-background">
        <div className="container mx-auto p-6">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">AI Agent Dashboard</h1>
              <p className="text-muted-foreground">
                Production-ready autonomous bug fixing and code generation system
              </p>
            </div>
            {getHealthBadge()}
          </div>

          {/* System Overview Cards */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Tickets</CardTitle>
                <AlertCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {metricsLoading ? '...' : systemMetrics?.total_tickets || 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  {systemMetrics?.active_tickets || 0} active
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {metricsLoading ? '...' : `${(systemMetrics?.success_rate || 0).toFixed(1)}%`}
                </div>
                <p className="text-xs text-muted-foreground">
                  {systemMetrics?.completed_tickets || 0} completed
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg Resolution</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {metricsLoading ? '...' : `${(systemMetrics?.avg_resolution_time || 0).toFixed(1)}h`}
                </div>
                <p className="text-xs text-muted-foreground">
                  Average time to fix
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">System Health</CardTitle>
                <Shield className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold capitalize">
                  {systemHealth?.overall_status || 'Unknown'}
                </div>
                <p className="text-xs text-muted-foreground">
                  {systemHealth?.alerts?.length || 0} active alerts
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Main Content Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList className="grid w-full grid-cols-6">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="health">Health</TabsTrigger>
              <TabsTrigger value="pipelines">Pipelines</TabsTrigger>
              <TabsTrigger value="tickets">Tickets</TabsTrigger>
              <TabsTrigger value="agents">Agents</TabsTrigger>
              <TabsTrigger value="analytics">Analytics</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4">
              <div className="grid gap-6 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Recent Activity</CardTitle>
                    <CardDescription>Latest ticket updates and agent actions</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {ticketsLoading ? (
                      <div className="space-y-2">
                        {[...Array(5)].map((_, i) => (
                          <div key={i} className="h-4 bg-gray-200 rounded animate-pulse" />
                        ))}
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {tickets?.slice(0, 5).map((ticket: any) => (
                          <div key={ticket.id} className="flex items-center space-x-4">
                            <div className={`w-2 h-2 rounded-full ${getStatusColor(ticket.status)}`} />
                            <div className="flex-1 space-y-1">
                              <p className="text-sm font-medium leading-none">
                                {ticket.title}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {ticket.jira_id} • {new Date(ticket.created_at).toLocaleString()}
                              </p>
                            </div>
                            <Badge variant="outline">{ticket.status}</Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <AgentStatus />
              </div>
            </TabsContent>

            <TabsContent value="health">
              <SystemHealth />
            </TabsContent>

            <TabsContent value="pipelines">
              <PipelineMonitor />
            </TabsContent>

            <TabsContent value="tickets">
              <TicketTable />
            </TabsContent>

            <TabsContent value="agents">
              <AgentStatus detailed={true} />
            </TabsContent>

            <TabsContent value="analytics">
              <MetricsCharts />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </WebSocketProvider>
  );
};

export default Dashboard;
