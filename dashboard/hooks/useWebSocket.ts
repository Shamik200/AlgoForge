'use client';

import { useState, useEffect, useCallback } from 'react';

/** WebSocket hook for real-time dashboard state updates. */
export function useWebSocket(url: string) {
  const [state, setState] = useState<any>(null);
  const [connected, setConnected] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(url);

    socket.onopen = () => {
      setConnected(true);
      // Request initial snapshot
      socket.send(JSON.stringify({ command: 'GET_SNAPSHOT' }));
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.system) {
          setState(data);
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);

    setWs(socket);
    return () => socket.close();
  }, [url]);

  const sendCommand = useCallback((command: string) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ command }));
    }
  }, [ws]);

  return { state, connected, sendCommand };
}
