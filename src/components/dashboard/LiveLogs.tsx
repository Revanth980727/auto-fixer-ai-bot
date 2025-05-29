
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Search, Download, Pause, Play, Filter } from 'lucide-react';
import { apiUrl } from '@/config/api';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  agent: string;
  message: string;
  execution_id?: string;
}

export const LiveLogs = () => {
  const [isLive, setIsLive] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [agentFilter, setAgentFilter] = useState('ALL');

  const { data: logs, isLoading, refetch } = useQuery({
    queryKey: ['live-logs'],
    queryFn: async () => {
      const response = await fetch(apiUrl('/api/logs?limit=100'));
      if (!response.ok) throw new Error('Failed to fetch logs');
      return response.json();
    },
    refetchInterval: isLive ? 2000 : false,
  });

  // Mock data for development
  const mockLogs: LogEntry[] = [
    {
      id: '1',
      timestamp: new Date().toISOString(),
      level: 'INFO',
      agent: 'intake',
      message: 'Polling JIRA for new tickets...',
      execution_id: 'exec_001'
    },
    {
      id: '2',
      timestamp: new Date(Date.now() - 5000).toISOString(),
      level: 'INFO',
      agent: 'planner',
      message: 'Analyzing ticket PROJ-123: TypeError in handleLogin function',
      execution_id: 'exec_002'
    },
    {
      id: '3',
      timestamp: new Date(Date.now() - 10000).toISOString(),
      level: 'ERROR',
      agent: 'developer',
      message: 'Failed to generate patch for ticket PROJ-124: OpenAI API rate limit exceeded',
      execution_id: 'exec_003'
    },
    {
      id: '4',
      timestamp: new Date(Date.now() - 15000).toISOString(),
      level: 'WARNING',
      agent: 'qa',
      message: 'Test suite failed for patch attempt 2/4',
      execution_id: 'exec_004'
    },
    {
      id: '5',
      timestamp: new Date(Date.now() - 20000).toISOString(),
      level: 'INFO',
      agent: 'communicator',
      message: 'Successfully created PR #456 for ticket PROJ-125',
      execution_id: 'exec_005'
    },
  ];

  const logData = isLoading ? mockLogs : logs || mockLogs;

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR': return 'bg-red-500';
      case 'WARNING': return 'bg-orange-500';
      case 'INFO': return 'bg-blue-500';
      case 'DEBUG': return 'bg-gray-500';
      default: return 'bg-gray-400';
    }
  };

  const getAgentIcon = (agent: string) => {
    switch (agent) {
      case 'intake': return '📥';
      case 'planner': return '🧠';
      case 'developer': return '👨‍💻';
      case 'qa': return '🧪';
      case 'communicator': return '📤';
      default: return '🤖';
    }
  };

  const filteredLogs = logData.filter((log: LogEntry) => {
    const matchesSearch = log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         log.agent.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesLevel = levelFilter === 'ALL' || log.level === levelFilter;
    const matchesAgent = agentFilter === 'ALL' || log.agent === agentFilter;
    
    return matchesSearch && matchesLevel && matchesAgent;
  });

  const exportLogs = () => {
    const logText = filteredLogs.map(log => 
      `[${log.timestamp}] ${log.level} ${log.agent}: ${log.message}`
    ).join('\n');
    
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent-logs-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center space-x-2">
              <span>Live System Logs</span>
              <Badge variant={isLive ? 'default' : 'secondary'}>
                {isLive ? 'Live' : 'Paused'}
              </Badge>
            </CardTitle>
            <CardDescription>Real-time agent execution logs</CardDescription>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsLive(!isLive)}
            >
              {isLive ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={exportLogs}
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="flex items-center space-x-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={levelFilter} onValueChange={setLevelFilter}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Levels</SelectItem>
              <SelectItem value="ERROR">Error</SelectItem>
              <SelectItem value="WARNING">Warning</SelectItem>
              <SelectItem value="INFO">Info</SelectItem>
              <SelectItem value="DEBUG">Debug</SelectItem>
            </SelectContent>
          </Select>
          <Select value={agentFilter} onValueChange={setAgentFilter}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Agents</SelectItem>
              <SelectItem value="intake">Intake</SelectItem>
              <SelectItem value="planner">Planner</SelectItem>
              <SelectItem value="developer">Developer</SelectItem>
              <SelectItem value="qa">QA</SelectItem>
              <SelectItem value="communicator">Communicator</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Log Display */}
        <ScrollArea className="h-96 w-full border rounded-lg p-4 bg-gray-50 dark:bg-gray-900">
          <div className="space-y-2 font-mono text-sm">
            {filteredLogs.map((log: LogEntry) => (
              <div key={log.id} className="flex items-start space-x-3 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
                <div className="flex items-center space-x-2 min-w-0">
                  <Badge className={`${getLevelColor(log.level)} text-white px-2 py-1 text-xs`}>
                    {log.level}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <div className="flex items-center space-x-1">
                    <span className="text-sm">{getAgentIcon(log.agent)}</span>
                    <span className="text-xs font-medium capitalize">{log.agent}</span>
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm break-words">{log.message}</p>
                  {log.execution_id && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Execution: {log.execution_id}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="text-xs text-muted-foreground text-center">
          Showing {filteredLogs.length} of {logData.length} log entries
          {isLive && ' • Auto-refreshing every 2 seconds'}
        </div>
      </CardContent>
    </Card>
  );
};
