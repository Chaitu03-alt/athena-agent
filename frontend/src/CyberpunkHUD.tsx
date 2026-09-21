import React, { useState, useEffect, useRef } from 'react';
import { TopBar, TelemetryData } from './components/TopBar';
import { LeftDrawer } from './components/LeftDrawer';
import { RightDrawer } from './components/RightDrawer';
import { TerminalFeed, FeedItem } from './components/TerminalFeed';
import { CommandInput } from './components/CommandInput';
import { audio } from './utils/audio';
import './styles/tokens.css';
import './styles/layout.css';

export const CyberpunkHUD: React.FC = () => {
  // Appearance & Audio State
  const [scanlines, setScanlines] = useState(true);
  const [isMuted, setIsMuted] = useState(() => audio.isMuted());

  // Drawer Toggles
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(true);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);

  // Live Telemetry
  const [telemetry, setTelemetry] = useState<TelemetryData>({
    cpu: 0,
    ram: 0,
    uptime: 0,
    state: 'idle',
    wsStatus: 'disconnected',
  });

  // Terminal Feed
  const [feedItems, setFeedItems] = useState<FeedItem[]>([
    {
      id: 'boot-1',
      type: 'boot',
      content: 'System initialized. Type a prompt or select a quick command to begin.',
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);

  const [isProcessing, setIsProcessing] = useState(false);
  const terminalBottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttempts = useRef(0);

  // Auto-scroll on new feed items
  useEffect(() => {
    terminalBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [feedItems]);

  // Audio Toggle
  const handleToggleMute = () => {
    const nextMuted = audio.toggleMute();
    setIsMuted(nextMuted);
  };

  // 1. Polling System Resources & State
  useEffect(() => {
    const fetchResources = async () => {
      try {
        const res = await fetch('/api/telemetry/resources');
        if (res.ok) {
          const data = await res.json();
          setTelemetry((prev) => ({
            ...prev,
            cpu: data.cpu_percent || 0,
            ram: data.ram_mb_used || 0,
            uptime: data.uptime_seconds || 0,
          }));
        }
      } catch {
        // Silent failover
      }
    };

    const fetchState = async () => {
      try {
        const res = await fetch('/api/telemetry/state');
        if (res.ok) {
          const data = await res.json();
          setTelemetry((prev) => ({
            ...prev,
            state: data.status || 'idle',
          }));
        }
      } catch {
        // Silent failover
      }
    };

    fetchResources();
    fetchState();
    const resInterval = setInterval(fetchResources, 2000);
    const stateInterval = setInterval(fetchState, 1000);

    return () => {
      clearInterval(resInterval);
      clearInterval(stateInterval);
    };
  }, []);

  // 2. WebSocket Telemetry Bus with Exponential Backoff
  useEffect(() => {
    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const defaultPath = '/api/telemetry/ws';
      const wsUrl =
        window.location.port === '5173'
          ? `ws://localhost:8000${defaultPath}`
          : `${protocol}//${window.location.host}${defaultPath}`;

      setTelemetry((prev) => ({ ...prev, wsStatus: 'reconnecting' }));
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempts.current = 0;
        setTelemetry((prev) => ({ ...prev, wsStatus: 'connected' }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const timestamp = new Date().toLocaleTimeString();

          if (data.event_type === 'tool_call') {
            audio.play('tool_start');
            const newToolNode: FeedItem = {
              id: `tool-${Date.now()}-${Math.random()}`,
              type: 'tool_call',
              content: '',
              timestamp,
              metadata: {
                toolName: data.payload?.tool_name || 'tool_call',
                arguments: data.payload?.arguments,
                status: 'running',
                rawPayload: data.payload,
              },
            };
            setFeedItems((prev) => [...prev, newToolNode]);
          } else if (data.event_type === 'tool_result') {
            audio.play('tool_end');
            // Resolve latest running tool node or append result
            setFeedItems((prev) => {
              const updated = [...prev];
              for (let i = updated.length - 1; i >= 0; i--) {
                if (updated[i].type === 'tool_call' && updated[i].metadata?.status === 'running') {
                  updated[i] = {
                    ...updated[i],
                    content: String(data.payload?.result || ''),
                    metadata: {
                      ...updated[i].metadata,
                      status: 'success',
                    },
                  };
                  return updated;
                }
              }
              // If none matched, append as fresh node
              return [
                ...updated,
                {
                  id: `res-${Date.now()}`,
                  type: 'tool_call',
                  content: String(data.payload?.result || ''),
                  timestamp,
                  metadata: {
                    toolName: data.payload?.tool_name || 'tool_result',
                    status: 'success',
                    rawPayload: data.payload,
                  },
                },
              ];
            });
          } else if (data.event_type === 'cron_alert') {
            audio.play('bell');
            setFeedItems((prev) => [
              ...prev,
              {
                id: `alert-${Date.now()}`,
                type: 'system_alert',
                content: data.payload?.message || 'Scheduled alert triggered.',
                timestamp,
              },
            ]);
          }
        } catch {
          // Payload parse failure
        }
      };

      ws.onclose = () => {
        setTelemetry((prev) => ({ ...prev, wsStatus: 'disconnected' }));
        // Exponential backoff reconnect
        const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts.current), 15000);
        reconnectAttempts.current += 1;
        reconnectTimeoutRef.current = window.setTimeout(connectWebSocket, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // 3. Command Execution Handler
  const handleExecuteCommand = async (cmd: string) => {
    if (cmd === '/clear') {
      audio.play('keystroke');
      setFeedItems([
        {
          id: `boot-${Date.now()}`,
          type: 'boot',
          content: 'Terminal feed cleared. Ready for operator input.',
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
      return;
    }

    const timestamp = new Date().toLocaleTimeString();
    const userItem: FeedItem = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: cmd,
      timestamp,
    };
    setFeedItems((prev) => [...prev, userItem]);
    setIsProcessing(true);

    try {
      const baseUrl = window.location.port === '5173' ? 'http://localhost:8000' : '';
      const res = await fetch(`${baseUrl}/api/terminal/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cmd }),
      });
      const data = await res.json();
      const content = data.content || 'Operation finished with empty response.';

      // Assistant Typewriter Simulation
      const assistantId = `asst-${Date.now()}`;
      const assistantItem: FeedItem = {
        id: assistantId,
        type: 'assistant',
        content,
        timestamp: new Date().toLocaleTimeString(),
      };

      setFeedItems((prev) => [...prev, assistantItem]);
      audio.play('tool_end');
    } catch (err: any) {
      audio.play('error');
      setFeedItems((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          type: 'error',
          content: `Terminal Execution Failed: ${err.message || String(err)}`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className={`crt-overlay ${scanlines ? 'crt-scanlines' : ''} hud-shell`}>
      {/* TopBar */}
      <TopBar
        telemetry={telemetry}
        scanlines={scanlines}
        onToggleScanlines={() => setScanlines((v) => !v)}
        isMuted={isMuted}
        onToggleMute={handleToggleMute}
        leftOpen={leftDrawerOpen}
        onToggleLeft={() => setLeftDrawerOpen((v) => !v)}
        rightOpen={rightDrawerOpen}
        onToggleRight={() => setRightDrawerOpen((v) => !v)}
      />

      {/* Body Area */}
      <div className="hud-body">
        {/* Left Drawer: Soul Profile & KV Store */}
        <LeftDrawer
          isOpen={leftDrawerOpen}
          onClose={() => setLeftDrawerOpen(false)}
        />

        {/* Main Stage Terminal */}
        <main className="hud-stage">
          {/* Terminal Scroll Feed */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col justify-between">
            <TerminalFeed items={feedItems} />
            <div ref={terminalBottomRef} />
          </div>

          {/* Fixed Command Input */}
          <CommandInput
            onExecute={handleExecuteCommand}
            disabled={isProcessing}
          />
        </main>

        {/* Right Drawer: Cron & Autonomous Schedulers */}
        <RightDrawer
          isOpen={rightDrawerOpen}
          onClose={() => setRightDrawerOpen(false)}
        />
      </div>
    </div>
  );
};
