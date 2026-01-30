import { useEffect, useRef, useState, useCallback } from "react";
import type {
  WebSocketEvent,
  WebSocketEventType,
  ScanProgressData,
  ScanCompleteData,
  NewAlertData,
} from "../types";

interface UseWebSocketOptions {
  onScanStarted?: (scanId: string) => void;
  onScanProgress?: (data: ScanProgressData) => void;
  onScanComplete?: (data: ScanCompleteData) => void;
  onScanError?: (error: string) => void;
  onNewAlert?: (data: NewAlertData) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastEvent: WebSocketEvent | null;
  reconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const optionsRef = useRef(options);

  // Keep options ref up to date
  optionsRef.current = options;

  const connect = useCallback(() => {
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Attempt to reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const wsEvent = JSON.parse(event.data) as WebSocketEvent;
        setLastEvent(wsEvent);

        const opts = optionsRef.current;
        switch (wsEvent.event as WebSocketEventType) {
          case "scan_started":
            opts.onScanStarted?.(wsEvent.data as string);
            break;
          case "scan_progress":
            opts.onScanProgress?.(wsEvent.data as ScanProgressData);
            break;
          case "scan_complete":
            opts.onScanComplete?.(wsEvent.data as ScanCompleteData);
            break;
          case "scan_error":
            opts.onScanError?.(wsEvent.data as string);
            break;
          case "new_alert":
            opts.onNewAlert?.(wsEvent.data as NewAlertData);
            break;
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    isConnected,
    lastEvent,
    reconnect: connect,
  };
}
