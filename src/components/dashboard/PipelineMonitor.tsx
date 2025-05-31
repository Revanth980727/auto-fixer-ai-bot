
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Clock, CheckCircle, AlertCircle, Play, Pause } from 'lucide-react';
import { apiUrl } from '@/config/api';

export const PipelineMonitor = () => {
  const { data: advancedMetrics, isLoading } = useQuery({
    queryKey: ['advanced-metrics'],
    queryFn: async () => {
      const response = await fetch(apiUrl('/api/metrics/advanced'));
      if (!response.ok) throw new Error('Failed to fetch advanced metrics');
      return response.json();
    },
    refetchInterval: 5000,
  });

  const pipelines = advancedMetrics?.pipeline_summary || [];

  const getStageIcon = (stage: string) => {
    switch (stage) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'in_progress': return <Play className="h-4 w-4 text-blue-500" />;
      default: return <Pause className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStageProgress = (currentStage: string) => {
    const stages = ['intake', 'planning', 'development', 'qa', 'communication', 'completed'];
    const currentIndex = stages.indexOf(currentStage);
    return currentIndex >= 0 ? ((currentIndex + 1) / stages.length) * 100 : 0;
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Monitor</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 rounded animate-pulse" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Play className="h-4 w-4" />
          Active Pipelines
        </CardTitle>
        <CardDescription>Real-time pipeline execution monitoring</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-96">
          <div className="space-y-4">
            {pipelines.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                No active pipelines
              </div>
            ) : (
              pipelines.map((pipeline: any) => (
                <div key={pipeline.context_id} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getStageIcon(pipeline.current_stage)}
                      <span className="font-medium">Ticket #{pipeline.ticket_id}</span>
                    </div>
                    <Badge variant={pipeline.has_errors ? 'destructive' : 'default'}>
                      {pipeline.current_stage}
                    </Badge>
                  </div>
                  
                  <Progress 
                    value={getStageProgress(pipeline.current_stage)} 
                    className="h-2"
                  />
                  
                  <div className="flex justify-between text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      <span>
                        {pipeline.total_duration ? `${pipeline.total_duration.toFixed(1)}s` : 'N/A'}
                      </span>
                    </div>
                    <span>
                      Stages: {pipeline.stages_completed} completed
                    </span>
                  </div>
                  
                  {pipeline.has_errors && (
                    <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                      Pipeline has encountered errors
                    </div>
                  )}
                  
                  {pipeline.checkpoints && pipeline.checkpoints.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {pipeline.checkpoints.map((checkpoint: string) => (
                        <Badge key={checkpoint} variant="outline" className="text-xs">
                          {checkpoint}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};
