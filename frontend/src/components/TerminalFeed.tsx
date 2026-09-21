import React, { useState } from 'react';
import { audio } from '../utils/audio';

export interface FeedItem {
  id: string;
  type: 'boot' | 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'system_alert' | 'error';
  content: string;
  timestamp: string;
  metadata?: {
    toolName?: string;
    arguments?: any;
    durationMs?: number;
    status?: 'success' | 'error' | 'denied' | 'running';
    rawPayload?: any;
    isStreaming?: boolean;
  };
}

interface TerminalFeedProps {
  items: FeedItem[];
  onSkipTypewriter?: (itemId: string) => void;
}

export const TerminalFeed: React.FC<TerminalFeedProps> = ({ items }) => {
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});
  const [rawJsonExpanded, setRawJsonExpanded] = useState<Record<string, boolean>>({});

  const toggleNode = (id: string) => {
    audio.play('keystroke');
    setExpandedNodes((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleRawJson = (id: string) => {
    audio.play('keystroke');
    setRawJsonExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex flex-col gap-3 font-mono text-xs">
      {items.map((item) => {
        if (item.type === 'boot') {
          return (
            <div key={item.id} className="text-[#6f9c82] opacity-80 border-b border-[#00ff66]/15 pb-2 mb-2 leading-relaxed">
              <pre className="text-[10px] text-[#00ff66] font-mono leading-none tracking-tighter mb-2 overflow-x-auto select-none">
{`    ___  ________  ________________   _____ 
   /   |/_  __/ / / / ____/   /   |  / ___/ 
  / /| | / / / /_/ / __/ / /| / /| |  \\__ \\  
 / ___ |/ / / __  / /___/ ___/ ___ | ___/ /  
/_/  |_/_/ /_/ /_/_____/_/  /_/  |_|/____/   `}
              </pre>
              <div className="text-[11px] text-[#e0f8e9]">ATHENA AUTONOMOUS KERNEL v5.0 // ONLINE</div>
              <div className="text-[10px] text-[#6f9c82]">Procedural Memory: Qdrant Hybrid + SQLite WAL Subsystem Active</div>
            </div>
          );
        }

        if (item.type === 'user') {
          return (
            <div key={item.id} className="flex items-start gap-2 text-[#00ff66] font-bold">
              <span className="text-[#00ff66] tracking-tight shrink-0 select-none">athena&gt;</span>
              <span className="text-[#e0f8e9] break-words whitespace-pre-wrap">{item.content}</span>
            </div>
          );
        }

        if (item.type === 'tool_call') {
          const isExpanded = expandedNodes[item.id] !== false; // default open
          const isRawOpen = !!rawJsonExpanded[item.id];
          const toolName = item.metadata?.toolName || 'tool_execution';
          const duration = item.metadata?.durationMs ? `[${item.metadata.durationMs}ms]` : '';
          const status = item.metadata?.status || 'success';

          return (
            <div key={item.id} className="tool-node-card p-2 ml-4 flex flex-col gap-1 text-[11px]">
              {/* Header */}
              <div
                onClick={() => toggleNode(item.id)}
                className="flex items-center justify-between cursor-pointer select-none text-cyan-300 hover:text-cyan-200"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold">{isExpanded ? '▾' : '▸'}</span>
                  <span className="bg-cyan-950/70 border border-cyan-400/40 px-1.5 py-0.5 text-[10px] font-bold tracking-wider text-cyan-400">
                    TOOL: {toolName}
                  </span>
                  {duration && (
                    <span className="text-[#6f9c82] text-[10px]">{duration}</span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-1 border border-[#00ff66]/30 text-[#00ff66]">
                    {status === 'success' ? '✓ EXECUTED' : status === 'error' ? '✕ FAILED' : '⚡ RUNNING'}
                  </span>
                </div>
              </div>

              {/* Node Body */}
              {isExpanded && (
                <div className="mt-1.5 flex flex-col gap-1.5 pl-3 border-l border-cyan-500/20">
                  {/* Arguments */}
                  {item.metadata?.arguments && (
                    <div className="text-[10px] text-[#6f9c82]">
                      <span className="text-cyan-400/80 font-semibold">ARGS: </span>
                      <span>
                        {typeof item.metadata.arguments === 'object'
                          ? JSON.stringify(item.metadata.arguments)
                          : String(item.metadata.arguments)}
                      </span>
                    </div>
                  )}

                  {/* Result Content */}
                  {item.content && (
                    <div className="bg-[#060608] border border-[#00ff66]/15 p-2 rounded text-[11px] text-[#e0f8e9] whitespace-pre-wrap font-mono max-h-40 overflow-y-auto">
                      {item.content}
                    </div>
                  )}

                  {/* Interactive Raw JSON Disclosure */}
                  {item.metadata?.rawPayload && (
                    <div className="mt-1">
                      <button
                        type="button"
                        onClick={() => toggleRawJson(item.id)}
                        className="text-[10px] text-[#6f9c82] hover:text-[#00ff66] flex items-center gap-1 cursor-pointer"
                      >
                        <span>[raw JSON {isRawOpen ? '▴' : '▾'}]</span>
                      </button>
                      {isRawOpen && (
                        <pre className="mt-1 p-2 bg-[#050508] border border-cyan-500/30 text-[10px] text-cyan-300 overflow-x-auto whitespace-pre-wrap">
                          {JSON.stringify(item.metadata.rawPayload, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        }

        if (item.type === 'system_alert') {
          return (
            <div key={item.id} className="p-2 ml-2 border border-amber-500/30 bg-amber-500/5 text-amber-300 text-xs flex items-center gap-2">
              <span className="text-amber-400 font-bold">🔔 CRON ALERT:</span>
              <span>{item.content}</span>
            </div>
          );
        }

        if (item.type === 'error') {
          return (
            <div key={item.id} className="p-2 ml-2 border border-[#ff3366]/40 bg-[#ff3366]/10 text-[#ff3366] text-xs flex items-center gap-2">
              <span className="font-bold">⛔ ERROR:</span>
              <span className="whitespace-pre-wrap break-all">{item.content}</span>
            </div>
          );
        }

        // Assistant Message (with Typewriter Reveal)
        return (
          <div key={item.id} className="flex flex-col gap-1 pl-2 border-l-2 border-[#00ff66]/40 my-1">
            <div className="text-[10px] text-[#6f9c82] flex items-center gap-2">
              <span className="text-[#00ff66] font-bold">ATHENA</span>
              <span>{item.timestamp}</span>
            </div>
            <div className="text-[#e0f8e9] text-xs leading-relaxed whitespace-pre-wrap break-words">
              {item.content}
            </div>
          </div>
        );
      })}
    </div>
  );
};
