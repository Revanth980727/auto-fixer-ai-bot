
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, Code, FileText, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { apiUrl } from '@/config/api';
import { useState } from 'react';

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
  const [openSections, setOpenSections] = useState<string[]>([]);

  const { data: executions, isLoading } = useQuery({
    queryKey: ['developer-debug'],
    queryFn: async (): Promise<DeveloperExecution[]> => {
      const response = await fetch(apiUrl('/api/developer-debug/executions'));
      if (!response.ok) throw new Error('Failed to fetch developer debug data');
      return response.json();
    },
    refetchInterval: 5000,
  });

  const { data: executionDetail } = useQuery({
    queryKey: ['developer-execution-detail', selectedExecution],
    queryFn: async (): Promise<DeveloperExecution> => {
      const response = await fetch(apiUrl(`/api/developer-debug/execution/${selectedExecution}`));
      if (!response.ok) throw new Error('Failed to fetch execution detail');
      return response.json();
    },
    enabled: !!selectedExecution,
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'running': return <Clock className="h-4 w-4 text-blue-500" />;
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
            Detailed execution logs and patch generation analysis
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
                      No developer executions found
                    </div>
                  ) : (
                    executions?.map((execution) => (
                      <div key={execution.execution_id} className="border rounded-lg p-4 space-y-3">
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
                          Started: {new Date(execution.started_at).toLocaleString()}
                          {execution.completed_at && (
                            <> • Completed: {new Date(execution.completed_at).toLocaleString()}</>
                          )}
                        </div>

                        <div className="flex justify-between text-sm">
                          <span>Patches: {execution.patch_attempts.length}</span>
                          <span>
                            Success: {execution.patch_attempts.filter(p => p.success).length}/
                            {execution.patch_attempts.length}
                          </span>
                        </div>

                        {execution.error_message && (
                          <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
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
                    <Badge variant={executionDetail.status === 'completed' ? 'default' : 'destructive'}>
                      {executionDetail.status}
                    </Badge>
                  </div>

                  <Collapsible 
                    open={openSections.includes('logs')}
                    onOpenChange={() => toggleSection('logs')}
                  >
                    <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 border rounded">
                      <ChevronDown className="h-4 w-4" />
                      <FileText className="h-4 w-4" />
                      Execution Logs
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <ScrollArea className="h-64 border rounded p-4 mt-2">
                        <pre className="text-xs whitespace-pre-wrap">
                          {executionDetail.logs || 'No logs available'}
                        </pre>
                      </ScrollArea>
                    </CollapsibleContent>
                  </Collapsible>

                  <Collapsible 
                    open={openSections.includes('patches')}
                    onOpenChange={() => toggleSection('patches')}
                  >
                    <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 border rounded">
                      <ChevronDown className="h-4 w-4" />
                      <Code className="h-4 w-4" />
                      Patch Attempts ({executionDetail.patch_attempts.length})
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="mt-2 space-y-2">
                        {executionDetail.patch_attempts.map((patch) => (
                          <div key={patch.id} className="border rounded p-3 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="font-medium">{patch.target_file}</span>
                              <div className="flex items-center gap-2">
                                <Badge variant={patch.success ? 'default' : 'destructive'}>
                                  {patch.success ? 'Success' : 'Failed'}
                                </Badge>
                                <span className="text-sm text-muted-foreground">
                                  Confidence: {(patch.confidence_score * 100).toFixed(1)}%
                                </span>
                              </div>
                            </div>
                            
                            {patch.patch_content && (
                              <ScrollArea className="h-32 bg-gray-50 p-2 rounded text-xs">
                                <pre>{patch.patch_content}</pre>
                              </ScrollArea>
                            )}
                          </div>
                        ))}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  {executionDetail.output_data && (
                    <Collapsible 
                      open={openSections.includes('output')}
                      onOpenChange={() => toggleSection('output')}
                    >
                      <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 border rounded">
                        <ChevronDown className="h-4 w-4" />
                        <FileText className="h-4 w-4" />
                        Output Data
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <ScrollArea className="h-32 border rounded p-4 mt-2">
                          <pre className="text-xs">
                            {JSON.stringify(executionDetail.output_data, null, 2)}
                          </pre>
                        </ScrollArea>
                      </CollapsibleContent>
                    </Collapsible>
                  )}
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  Select an execution from the list to view details
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};
