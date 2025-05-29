
import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { toast } from '@/hooks/use-toast';
import { API_CONFIG } from '@/config/api';

interface WebSocketContextType {
  socket: WebSocket | null;
  connected: boolean;
  sendMessage: (message: any) => void;
}

const WebSocketContext = createContext<WebSocketContextType>({
  socket: null,
  connected: false,
  sendMessage: () => {},
});

export const useWebSocket = () => useContext(WebSocketContext);

interface WebSocketProviderProps {
  children: React.ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = () => {
    try {
      const ws = new WebSocket(API_CONFIG.wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected to', API_CONFIG.wsUrl);
        setConnected(true);
        reconnectAttempts.current = 0;
        
        toast({
          title: "Connected",
          description: "Real-time updates are now active.",
        });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message received:', data);
          
          // Handle different message types
          switch (data.type) {
            case 'ticket_update':
              toast({
                title: "Ticket Updated",
                description: `${data.ticket_id}: ${data.status}`,
              });
              // Trigger query refetch for tickets
              window.dispatchEvent(new CustomEvent('ticket-update', { detail: data }));
              break;
            case 'agent_status':
              console.log('Agent status update:', data);
              window.dispatchEvent(new CustomEvent('agent-status', { detail: data }));
              break;
            case 'system_alert':
              toast({
                title: data.title || "System Alert",
                description: data.message,
                variant: data.severity === 'error' ? 'destructive' : 'default',
              });
              break;
            case 'log_entry':
              window.dispatchEvent(new CustomEvent('new-log', { detail: data }));
              break;
            default:
              console.log('Unknown message type:', data.type);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        setSocket(null);

        // Attempt to reconnect
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const timeout = Math.pow(2, reconnectAttempts.current) * 1000; // Exponential backoff
          reconnectAttempts.current++;
          
          console.log(`Attempting to reconnect in ${timeout}ms (attempt ${reconnectAttempts.current})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, timeout);
        } else {
          toast({
            title: "Connection Lost",
            description: "Unable to reconnect to real-time updates. Please refresh the page.",
            variant: "destructive",
          });
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      setSocket(ws);
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  };

  const sendMessage = (message: any) => {
    if (socket && connected) {
      socket.send(JSON.stringify(message));
    }
  };

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socket) {
        socket.close();
      }
    };
  }, []);

  return (
    <WebSocketContext.Provider value={{ socket, connected, sendMessage }}>
      {children}
    </WebSocketContext.Provider>
  );
};
