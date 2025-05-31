import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { apiUrl } from '@/config/api';
import { MetricsChartsData, PerformanceTrends } from '@/types/metrics';

export const MetricsCharts = () => {
  const { data: metricsData, isLoading } = useQuery({
    queryKey: ['metrics-charts'],
    queryFn: async (): Promise<MetricsChartsData> => {
      const response = await fetch(apiUrl('/api/metrics/charts'));
      if (!response.ok) throw new Error('Failed to fetch metrics data');
      return response.json();
    },
    refetchInterval: 30000,
  });

  const { data: performanceTrends } = useQuery({
    queryKey: ['performance-trends'],
    queryFn: async (): Promise<PerformanceTrends> => {
      const response = await fetch(apiUrl('/api/metrics/performance-trends?hours=24'));
      if (!response.ok) throw new Error('Failed to fetch performance trends');
      return response.json();
    },
    refetchInterval: 60000,
  });

  // Enhanced mock data with real structure
  const mockData: MetricsChartsData = {
    successRate: [
      { date: '2024-01-01', rate: 85 },
      { date: '2024-01-02', rate: 88 },
      { date: '2024-01-03', rate: 92 },
      { date: '2024-01-04', rate: 87 },
      { date: '2024-01-05', rate: 94 },
    ],
    agentActivity: [
      { agent: 'Intake', tasks: 45, success_rate: 95, avg_duration: 2.1 },
      { agent: 'Planner', tasks: 38, success_rate: 89, avg_duration: 8.3 },
      { agent: 'Developer', tasks: 42, success_rate: 82, avg_duration: 45.2 },
      { agent: 'QA', tasks: 35, success_rate: 91, avg_duration: 12.7 },
      { agent: 'Communicator', tasks: 40, success_rate: 97, avg_duration: 3.4 },
    ],
    errorTypes: [
      { name: 'Agent Failures', value: 8, color: '#ff6b6b' },
      { name: 'Pipeline Errors', value: 5, color: '#4ecdc4' },
      { name: 'GitHub API Errors', value: 3, color: '#45b7d1' },
      { name: 'Context Validation', value: 2, color: '#96ceb4' },
      { name: 'Other', value: 1, color: '#ffeaa7' },
    ],
  };

  const data = isLoading ? mockData : metricsData || mockData;

  if (isLoading) {
    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {[...Array(6)].map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <div className="h-4 bg-gray-200 rounded animate-pulse" />
            </CardHeader>
            <CardContent>
              <div className="h-64 bg-gray-200 rounded animate-pulse" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle>Success Rate Trend</CardTitle>
          <CardDescription>AI agent success rate over the last 7 days</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data.successRate}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="rate" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Error Distribution</CardTitle>
          <CardDescription>Types of errors encountered</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data.errorTypes}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {data.errorTypes.map((entry, index: number) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle>Agent Performance</CardTitle>
          <CardDescription>Tasks processed and success rates by agent</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.agentActivity}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="agent" />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" domain={[0, 100]} />
              <Tooltip />
              <Legend />
              <Bar yAxisId="left" dataKey="tasks" fill="#8884d8" name="Tasks" />
              <Bar yAxisId="right" dataKey="success_rate" fill="#82ca9d" name="Success Rate %" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Execution Times</CardTitle>
          <CardDescription>Average agent execution duration</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.agentActivity} layout="horizontal">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="agent" type="category" />
              <Tooltip formatter={(value) => [`${value}s`, 'Avg Duration']} />
              <Bar dataKey="avg_duration" fill="#ffc658" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {performanceTrends && Object.keys(performanceTrends).length > 0 && (
        <Card className="md:col-span-3">
          <CardHeader>
            <CardTitle>Performance Trends (24h)</CardTitle>
            <CardDescription>Real-time performance metrics and trends</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              {(Object.keys(performanceTrends) as Array<keyof PerformanceTrends>).map((metric) => {
                const trendData = performanceTrends[metric];
                
                return (
                  <div key={metric} className="p-4 border rounded-lg">
                    <h4 className="font-medium text-sm mb-2">{String(metric).replace(/_/g, ' ')}</h4>
                    <div className="text-2xl font-bold">{trendData.avg_value?.toFixed(2) || 'N/A'}</div>
                    <div className={`text-sm ${
                      trendData.trend_direction === 'increasing' ? 'text-red-500' : 
                      trendData.trend_direction === 'decreasing' ? 'text-green-500' : 'text-gray-500'
                    }`}>
                      {trendData.trend_direction} trend
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {trendData.data_points} data points
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
