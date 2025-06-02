
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, Code, FileText, AlertCircle, CheckCircle, Clock, Timer } from 'lucide-react';
import { apiUrl } from '@/config/api';
import { useState } from 'react';
import { useToast } from '@/hooks/use-toast';

interface PatchAttempt {
  id: number;
  target_file: string;
  confidence_score: number;
  success: boolean;
  patch_content?: string;
  patched_code?: string;
  test_code?: string;
  patch_content_preview?: string;
  created_at: string;
}

interface DeveloperExecution {
  execution_id: number;
  ticket_id: number;
  ticket_title: string;
  status: string;
  logs: string;
  output_data: any;
  error_message: string | null;
  patch_attempts: PatchAttempt[];
  started_at: string;
  completed_at: string | null;
}

export const DeveloperDebug = () => {
  const [selectedExecution, setSelectedExecution] = useState<number | null>(null);
  const [openSections, setOpenSections] = useState<string[]>(['logs']);
  const { toast } = useToast();

  const { data: executions, isLoading, error } = useQuery({
    queryKey: ['developer-debug'],
    queryFn: async (): Promise<DeveloperExecution[]> => {
      console.log('🔍 Fetching developer debug data...');
      const response = await fetch(apiUrl('/api/developer-debug/executions'));
      if (!response.ok) {
        console.error('❌ Failed to fetch developer debug data:', response.status, response.statusText);
        throw new Error(`Failed to fetch developer debug data: ${response.status}`);
      }
      const data = await response.json();
      console.log('✅ Developer debug data loaded:', data.length, 'executions');
      return data;
    },
    refetchInterval: 5000,
    onError: (error) => {
      console.error('❌ Developer debug query error:', error);
      toast({
        title: "Error Loading Debug Data",
        description: "Failed to load developer execution data. Check console for details.",
        variant: "destructive",
      });
    }
  });

  const { data: executionDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['developer-execution-detail', selectedExecution],
    queryFn: async (): Promise<DeveloperExecution> => {
      console.log('🔍 Fetching execution detail for:', selectedExecution);
      const response = await fetch(apiUrl(`/api/developer-debug/execution/${selectedExecution}`));
      if (!response.ok) {
        console.error('❌ Failed to fetch execution detail:', response.status);
        throw new Error(`Failed to fetch execution detail: ${response.status}`);
      }
      const data = await response.json();
      console.log('✅ Execution detail loaded:', data);
      return data;
    },
    enabled: !!selectedExecution,
    onError: (error) => {
      console.error('❌ Execution detail error:', error);
      toast({
        title: "Error Loading Execution Detail",
        description: "Failed to load execution details. Check console for details.",
        variant: "destructive",
      });
    }
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'running': return <Timer className="h-4 w-4 text-blue-500 animate-spin" />;
      default: return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const toggleSection = (section: string) => {
    setOpenSections(prev => 
      prev.includes(section) 
        ? prev.filter(s => s !== section)
        : [...prev, section]
    );
  };

  const formatDuration = (started: string, completed?: string | null) => {
    const start = new Date(started);
    const end = completed ? new Date(completed) : new Date();
    const duration = Math.round((end.getTime() - start.getTime()) / 1000);
    return `${duration}s`;
  };

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            Developer Agent Debug - Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-red-600 py-8">
            <p className="font-medium">Failed to load debug data</p>
            <p className="text-sm mt-2">Error: {error.message}</p>
            <Button 
              variant="outline" 
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Developer Agent Debug</CardTitle>
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
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code className="h-4 w-4" />
            Developer Agent Debug Console
          </CardTitle>
          <CardDescription>
            Enhanced execution logs, patch generation analysis, and OpenAI timing metrics
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="executions" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="executions">Recent Executions</TabsTrigger>
              <TabsTrigger value="detail">Execution Detail</TabsTrigger>
            </TabsList>

            <TabsContent value="executions" className="space-y-4">
              <ScrollArea className="h-96">
                <div className="space-y-4">
                  {executions?.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      <AlertCircle className="h-8 w-8 mx-auto mb-2" />
                      <p>No developer executions found</p>
                      <p className="text-sm mt-1">Executions will appear here once the developer agent starts processing tickets</p>
                    </div>
                  ) : (
                    executions?.map((execution) => (
                      <div key={execution.execution_id} className="border rounded-lg p-4 space-y-3 hover:bg-gray-50 transition-colors">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(execution.status)}
                            <span className="font-medium">
                              Ticket #{execution.ticket_id}: {execution.ticket_title}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={execution.status === 'completed' ? 'default' : 'destructive'}>
                              {execution.status}
                            </Badge>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setSelectedExecution(execution.execution_id)}
                            >
                              View Details
                            </Button>
                          </div>
                        </div>
                        
                        <div className="text-sm text-muted-foreground">
                          <div className="flex items-center gap-4">
                            <span>Started: {new Date(execution.started_at).toLocaleString()}</span>
                            {execution.completed_at && (
                              <span>Duration: {formatDuration(execution.started_at, execution.completed_at)}</span>
                            )}
                          </div>
                        </div>

                        <div className="flex justify-between items-center text-sm">
                          <span>Patches: {execution.patch_attempts.length}</span>
                          <span className="flex items-center gap-2">
                            Success: {execution.patch_attempts.filter(p => p.success).length}/
                            {execution.patch_attempts.length}
                            {execution.patch_attempts.length > 0 && (
                              <Badge variant="outline" className="text-xs">
                                {((execution.patch_attempts.filter(p => p.success).length / execution.patch_attempts.length) * 100).toFixed(0)}%
                              </Badge>
                            )}
                          </span>
                        </div>

                        {execution.error_message && (
                          <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                            <AlertCircle className="h-3 w-3 inline mr-1" />
                            Error: {execution.error_message}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="detail" className="space-y-4">
              {selectedExecution && executionDetail ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">
                      Execution #{executionDetail.execution_id}
                    </h3>
                    <div className="flex items-center gap-2">
                      <Badge variant={executionDetail.status === 'completed' ? 'default' : 'destructive'}>
                        {executionDetail.status}
                      </Badge>
                      {executionDetail.completed_at && (
                        <Badge variant="outline">
                          {formatDuration(executionDetail.started_at, executionDetail.completed_at)}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <Collapsible 
                    open={openSections.includes('logs')}
                    onOpenChange={() => toggleSection('logs')}
                  >
                    <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 border rounded hover:bg-gray-50">
                      <ChevronDown className={`h-4 w-4 transition-transform ${openSections.includes('logs') ? 'rotate-180' : ''}`} />
                      <FileText className="h-4 w-4" />
                      Execution Logs & Debug Info
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <ScrollArea className="h-64 border rounded p-4 mt-2 bg-gray-50">
                        <pre className="text-xs whitespace-pre-wrap font-mono">
                          {executionDetail.logs || 'No logs available'}
                        </pre>
                      </ScrollArea>
                    </CollapsibleContent>
                  </Collapsible>

                  <Collapsible 
                    open={openSections.includes('patches')}
                    onOpenChange={() => toggleSection('patches')}
                  >
                    <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 border rounded hover:bg-gray-50">
                      <ChevronDown className={`h-4 w-4 transition-transform ${openSections.includes('patches') ? 'rotate-180' : ''}`} />
                      <Code className="h-4 w-4" />
                      Patch Attempts ({executionDetail.patch_attempts.length})
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="mt-2 space-y-2">
                        {executionDetail.patch_attempts.length === 0 ? (
                          <div className="text-center text-muted-foreground py-4">
                            No patch attempts recorded
                          </div>
                        ) : (
                          executionDetail.patch_attempts.map((patch) => (
                            <div key={patch.id} className="border rounded p-3 space-y-2 bg-white">
                              <div className="flex items-center justify-between">
                                <span className="font-medium text-sm">{patch.target_file}</span>
                                <div className="flex items-center gap-2">
                                  <Badge variant={patch.success ? 'default' : 'destructive'} className="text-xs">
                                    {patch.success ? 'Success' : 'Failed'}
                                  </Badge>
                                  <span className="text-xs text-muted-foreground">
                                    Confidence: {(patch.confidence_score * 100).toFixed(1)}%
                                  </span>
                                </div>
                              </div>
                              
                              {patch.patch_content && (
                                <ScrollArea className="h-32 bg-gray-50 p-2 rounded text-xs">
                                  <pre className="font-mono">{patch.patch_content}</pre>
                                </ScrollArea>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  {executionDetail.output_data && (
                    <Collapsible 
                      open={openSections.includes('output')}
                      onOpenChange={() => toggleSection('output')}
                    >
                      <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 border rounded hover:bg-gray-50">
                        <ChevronDown className={`h-4 w-4 transition-transform ${openSections.includes('output') ? 'rotate-180' : ''}`} />
                        <FileText className="h-4 w-4" />
                        Output Data & Metrics
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <ScrollArea className="h-32 border rounded p-4 mt-2 bg-gray-50">
                          <pre className="text-xs font-mono">
                            {JSON.stringify(executionDetail.output_data, null, 2)}
                          </pre>
                        </ScrollArea>
                      </CollapsibleContent>
                    </Collapsible>
                  )}
                </div>
              ) : detailLoading ? (
                <div className="text-center py-8">
                  <Timer className="h-8 w-8 mx-auto mb-2 animate-spin" />
                  <p>Loading execution details...</p>
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  <Code className="h-8 w-8 mx-auto mb-2" />
                  <p>Select an execution from the list to view details</p>
                  <p className="text-sm mt-1">Detailed logs, patches, and timing information will appear here</p>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};
