
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Switch } from '@/components/ui/switch';
import { Bot, Activity, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import { toast } from '@/hooks/use-toast';

interface AgentStatusProps {
  detailed?: boolean;
}

export const AgentStatus = ({ detailed = false }: AgentStatusProps) => {
  const { data: agentStatus, isLoading, refetch } = useQuery({
    queryKey: ['agent-status'],
    queryFn: async () => {
      const response = await fetch('http://localhost:8000/api/agents/status');
      if (!response.ok) throw new Error('Failed to fetch agent status');
      return response.json();
    },
    refetchInterval: 10000,
  });

  const toggleAgent = async (agentType: string, currentStatus: boolean) => {
    try {
      const response = await fetch(`http://localhost:8000/api/agents/${agentType}/toggle`, {
        method: 'POST',
      });
      
      if (!response.ok) throw new Error('Failed to toggle agent');
      
      toast({
        title: "Agent Updated",
        description: `${agentType} agent has been ${currentStatus ? 'disabled' : 'enabled'}.`,
      });
      
      refetch();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to toggle agent. Please try again.",
        variant: "destructive",
      });
    }
  };

  const getAgentIcon = (agentType: string) => {
    switch (agentType) {
      case 'intake': return '📥';
      case 'planner': return '🧠';
      case 'developer': return '👨‍💻';
      case 'qa': return '🧪';
      case 'communicator': return '📤';
      default: return '🤖';
    }
  };

  const getAgentDescription = (agentType: string) => {
    switch (agentType) {
      case 'intake': return 'Monitors JIRA for new bug tickets';
      case 'planner': return 'Analyzes bugs and creates execution plans';
      case 'developer': return 'Generates code patches using GPT-4';
      case 'qa': return 'Tests patches in isolated environments';
      case 'communicator': return 'Creates PRs and updates tickets';
      default: return 'AI agent component';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Agent Status</CardTitle>
          <CardDescription>Loading agent information...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 rounded animate-pulse" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (detailed) {
    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {agentStatus?.map((agent: any) => (
          <Card key={agent.agent_type}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-2xl">{getAgentIcon(agent.agent_type)}</span>
                  <div>
                    <CardTitle className="text-lg capitalize">
                      {agent.agent_type.replace('_', ' ')} Agent
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {getAgentDescription(agent.agent_type)}
                    </CardDescription>
                  </div>
                </div>
                <Switch
                  checked={agent.enabled}
                  onCheckedChange={() => toggleAgent(agent.agent_type, agent.enabled)}
                />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Status</span>
                <Badge variant={agent.enabled ? 'default' : 'secondary'}>
                  {agent.enabled ? 'Active' : 'Disabled'}
                </Badge>
              </div>

              {agent.enabled && (
                <>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>Success Rate</span>
                      <span>{(agent.success_rate * 100).toFixed(1)}%</span>
                    </div>
                    <Progress value={agent.success_rate * 100} className="h-2" />
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="flex items-center space-x-1">
                      <Activity className="h-4 w-4 text-blue-500" />
                      <span className="text-muted-foreground">Active:</span>
                      <span className="font-medium">{agent.active_executions}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Clock className="h-4 w-4 text-orange-500" />
                      <span className="text-muted-foreground">Avg:</span>
                      <span className="font-medium">{agent.avg_response_time.toFixed(1)}s</span>
                    </div>
                  </div>

                  {agent.last_activity && (
                    <div className="text-xs text-muted-foreground">
                      Last active: {new Date(agent.last_activity).toLocaleString()}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Bot className="h-5 w-5" />
          <span>Agent Status</span>
        </CardTitle>
        <CardDescription>Real-time status of AI agents</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {agentStatus?.map((agent: any) => (
            <div key={agent.agent_type} className="flex items-center justify-between p-3 border rounded-lg">
              <div className="flex items-center space-x-3">
                <span className="text-lg">{getAgentIcon(agent.agent_type)}</span>
                <div>
                  <div className="font-medium capitalize">
                    {agent.agent_type.replace('_', ' ')}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {agent.active_executions} active • {(agent.success_rate * 100).toFixed(0)}% success
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {agent.enabled ? (
                  <Badge variant="default" className="bg-green-500">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Active
                  </Badge>
                ) : (
                  <Badge variant="secondary">
                    <AlertCircle className="w-3 h-3 mr-1" />
                    Disabled
                  </Badge>
                )}
                <Switch
                  checked={agent.enabled}
                  onCheckedChange={() => toggleAgent(agent.agent_type, agent.enabled)}
                />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
