
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export const MetricsCharts = () => {
  const { data: metricsData, isLoading } = useQuery({
    queryKey: ['metrics-charts'],
    queryFn: async () => {
      const response = await fetch('http://localhost:8000/api/metrics/charts');
      if (!response.ok) throw new Error('Failed to fetch metrics data');
      return response.json();
    },
    refetchInterval: 30000,
  });

  // Mock data for development
  const mockData = {
    successRate: [
      { date: '2024-01-01', rate: 85 },
      { date: '2024-01-02', rate: 88 },
      { date: '2024-01-03', rate: 92 },
      { date: '2024-01-04', rate: 87 },
      { date: '2024-01-05', rate: 94 },
    ],
    agentActivity: [
      { agent: 'Intake', tasks: 45 },
      { agent: 'Planner', tasks: 38 },
      { agent: 'Developer', tasks: 42 },
      { agent: 'QA', tasks: 35 },
      { agent: 'Communicator', tasks: 40 },
    ],
    errorTypes: [
      { name: 'Syntax Error', value: 30, color: '#ff6b6b' },
      { name: 'Logic Error', value: 25, color: '#4ecdc4' },
      { name: 'Runtime Error', value: 20, color: '#45b7d1' },
      { name: 'Import Error', value: 15, color: '#96ceb4' },
      { name: 'Other', value: 10, color: '#ffeaa7' },
    ],
  };

  const data = isLoading ? mockData : metricsData || mockData;

  if (isLoading) {
    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {[...Array(3)].map((_, i) => (
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
          <CardDescription>AI agent success rate over time</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.successRate}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="rate" stroke="#8884d8" strokeWidth={2} />
            </LineChart>
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
                {data.errorTypes.map((entry: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="md:col-span-2 lg:col-span-3">
        <CardHeader>
          <CardTitle>Agent Activity</CardTitle>
          <CardDescription>Tasks processed by each agent</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.agentActivity}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="agent" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="tasks" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
};
