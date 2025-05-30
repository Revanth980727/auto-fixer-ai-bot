
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RotateCcw, AlertTriangle, Eye, Filter } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { PatchDiffViewer } from './PatchDiffViewer';

interface Ticket {
  id: number;
  jira_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  created_at: string;
  updated_at: string;
  retry_count: number;
  assigned_agent: string | null;
}

export const TicketTable = () => {
  const [filters, setFilters] = useState({
    status: '',
    priority: '',
    search: ''
  });
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);

  // Build query parameters
  const queryParams = new URLSearchParams();
  if (filters.status) queryParams.append('status', filters.status);
  if (filters.priority) queryParams.append('priority', filters.priority);

  const { data: tickets, isLoading, refetch } = useQuery({
    queryKey: ['tickets', filters],
    queryFn: async () => {
      const response = await fetch(`http://localhost:8000/api/tickets?${queryParams.toString()}`);
      if (!response.ok) throw new Error('Failed to fetch tickets');
      return response.json();
    },
    refetchInterval: 15000,
  });

  const { data: ticketDetail } = useQuery({
    queryKey: ['ticket-detail', selectedTicket?.id],
    queryFn: async () => {
      if (!selectedTicket) return null;
      const response = await fetch(`http://localhost:8000/api/tickets/${selectedTicket.id}`);
      if (!response.ok) throw new Error('Failed to fetch ticket details');
      return response.json();
    },
    enabled: !!selectedTicket,
  });

  const handleRetry = async (ticketId: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/tickets/${ticketId}/retry`, {
        method: 'POST',
      });
      
      if (!response.ok) throw new Error('Failed to retry ticket');
      
      toast({
        title: "Ticket Retried",
        description: "The ticket has been queued for retry processing.",
      });
      
      refetch();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to retry ticket. Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleEscalate = async (ticketId: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/tickets/${ticketId}/escalate`, {
        method: 'POST',
      });
      
      if (!response.ok) throw new Error('Failed to escalate ticket');
      
      toast({
        title: "Ticket Escalated",
        description: "The ticket has been escalated for human review.",
      });
      
      refetch();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to escalate ticket. Please try again.",
        variant: "destructive",
      });
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'default';
      case 'failed': return 'destructive';
      case 'in_progress': return 'secondary';
      case 'escalated': return 'outline';
      default: return 'secondary';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'destructive';
      case 'medium': return 'outline';
      case 'low': return 'secondary';
      default: return 'secondary';
    }
  };

  const filteredTickets = tickets?.filter((ticket: Ticket) => {
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      return (
        ticket.title.toLowerCase().includes(searchLower) ||
        ticket.jira_id.toLowerCase().includes(searchLower) ||
        ticket.description.toLowerCase().includes(searchLower)
      );
    }
    return true;
  }) || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Ticket Management</span>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RotateCcw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </CardTitle>
        <CardDescription>
          Monitor and manage bug tickets in the autonomous fixing pipeline
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Filters */}
        <div className="flex gap-4 mb-6">
          <Input
            placeholder="Search tickets..."
            value={filters.search}
            onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
            className="max-w-sm"
          />
          
          <Select value={filters.status} onValueChange={(value) => setFilters(prev => ({ ...prev, status: value }))}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Statuses</SelectItem>
              <SelectItem value="todo">To Do</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="testing">Testing</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="escalated">Escalated</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filters.priority} onValueChange={(value) => setFilters(prev => ({ ...prev, priority: value }))}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Priorities</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Tickets Table */}
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticket ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Retries</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                [...Array(5)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(8)].map((_, j) => (
                      <TableCell key={j}>
                        <div className="h-4 bg-gray-200 rounded animate-pulse" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filteredTickets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                    No tickets found matching your criteria.
                  </TableCell>
                </TableRow>
              ) : (
                filteredTickets.map((ticket: Ticket) => (
                  <TableRow key={ticket.id}>
                    <TableCell className="font-mono">{ticket.jira_id}</TableCell>
                    <TableCell className="max-w-xs truncate">{ticket.title}</TableCell>
                    <TableCell>
                      <Badge variant={getStatusColor(ticket.status)}>
                        {ticket.status.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getPriorityColor(ticket.priority)}>
                        {ticket.priority}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {ticket.assigned_agent || '-'}
                    </TableCell>
                    <TableCell>
                      {ticket.retry_count > 0 && (
                        <Badge variant="outline" className="text-orange-600">
                          {ticket.retry_count}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(ticket.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => setSelectedTicket(ticket)}
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                              <DialogTitle>{ticket.title}</DialogTitle>
                              <DialogDescription>
                                {ticket.jira_id} • Created {new Date(ticket.created_at).toLocaleString()}
                              </DialogDescription>
                            </DialogHeader>
                            
                            <Tabs defaultValue="overview" className="w-full">
                              <TabsList className="grid w-full grid-cols-3">
                                <TabsTrigger value="overview">Overview</TabsTrigger>
                                <TabsTrigger value="patches">Patches</TabsTrigger>
                                <TabsTrigger value="executions">Executions</TabsTrigger>
                              </TabsList>
                              
                              <TabsContent value="overview" className="space-y-4">
                                <div>
                                  <h4 className="font-semibold mb-2">Description</h4>
                                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                                    {ticketDetail?.description || ticket.description}
                                  </p>
                                </div>
                                
                                {ticketDetail?.error_trace && (
                                  <div>
                                    <h4 className="font-semibold mb-2">Error Trace</h4>
                                    <pre className="text-xs bg-muted p-4 rounded-lg overflow-x-auto">
                                      {ticketDetail.error_trace}
                                    </pre>
                                  </div>
                                )}
                              </TabsContent>
                              
                              <TabsContent value="patches">
                                {ticketDetail?.patches ? (
                                  <PatchDiffViewer patches={ticketDetail.patches} />
                                ) : (
                                  <p className="text-muted-foreground">Loading patches...</p>
                                )}
                              </TabsContent>
                              
                              <TabsContent value="executions" className="space-y-4">
                                {ticketDetail?.executions && ticketDetail.executions.length > 0 ? (
                                  <div className="space-y-2">
                                    {ticketDetail.executions.map((execution: any) => (
                                      <div key={execution.id} className="border rounded p-3">
                                        <div className="flex items-center justify-between mb-2">
                                          <Badge>{execution.agent_type}</Badge>
                                          <Badge variant={execution.status === 'completed' ? 'default' : 'destructive'}>
                                            {execution.status}
                                          </Badge>
                                        </div>
                                        {execution.logs && (
                                          <pre className="text-xs bg-muted p-2 rounded mt-2 overflow-x-auto">
                                            {execution.logs}
                                          </pre>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-muted-foreground">No executions found.</p>
                                )}
                              </TabsContent>
                            </Tabs>
                          </DialogContent>
                        </Dialog>
                        
                        {ticket.status === 'failed' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRetry(ticket.id)}
                          >
                            <RotateCcw className="w-4 h-4" />
                          </Button>
                        )}
                        
                        {['failed', 'in_progress'].includes(ticket.status) && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEscalate(ticket.id)}
                          >
                            <AlertTriangle className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
};
