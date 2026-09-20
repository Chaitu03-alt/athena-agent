import React, { useState } from 'react';
import { Plus, MessageSquare, Trash2, Search, Cpu, Brain } from 'lucide-react';
import { SessionItem } from '../api/client';

interface Props {
  sessions: SessionItem[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onOpenMemoryDrawer?: () => void;
}

export const Sidebar: React.FC<Props> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onOpenMemoryDrawer,
}) => {
  const [filter, setFilter] = useState('');

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <aside className="w-64 md:w-72 bg-dark-900 border-r border-dark-800 flex flex-col h-full flex-shrink-0 select-none">
      {/* App Header */}
      <div className="p-4 border-b border-dark-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-brand-600/20 border border-brand-500/30 flex items-center justify-center text-brand-500">
            <Cpu size={16} />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100 tracking-tight">Adaptive Agent</h1>
            <p className="text-[11px] text-slate-500">Phase 1: Chat + Memory</p>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-white bg-brand-600 hover:bg-brand-500 active:bg-brand-700 rounded-lg transition-all shadow-sm shadow-brand-500/20"
        >
          <Plus size={15} />
          <span>New Chat</span>
        </button>
      </div>

      {/* Search Input */}
      {sessions.length > 3 && (
        <div className="px-3 pb-2">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search chats..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full bg-dark-950 border border-dark-800 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500"
            />
          </div>
        </div>
      )}

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        <div className="px-2 py-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          Sessions ({sessions.length})
        </div>

        {filteredSessions.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500">
            {filter ? 'No matching chats' : 'No chats yet'}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            return (
              <div
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={`group flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer text-xs transition-all ${
                  isActive
                    ? 'bg-dark-800 text-slate-100 font-medium border border-dark-700 shadow-sm'
                    : 'text-slate-400 hover:bg-dark-850 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <MessageSquare
                    size={14}
                    className={`flex-shrink-0 ${isActive ? 'text-brand-500' : 'text-slate-500'}`}
                  />
                  <span className="truncate">{session.title}</span>
                </div>

                <div className="flex items-center gap-1.5 ml-2">
                  <span className="text-[10px] text-slate-500 group-hover:hidden">
                    {session.message_count}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 rounded transition-opacity"
                    title="Delete session"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Memory Inspector Navigation Button */}
      <div className="p-3 border-t border-dark-800">
        <button
          onClick={onOpenMemoryDrawer}
          className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-200 hover:text-white bg-dark-850 hover:bg-dark-800 border border-dark-700 hover:border-brand-500/40 rounded-lg transition-all shadow-sm group"
        >
          <span className="flex items-center gap-2">
            <Brain size={14} className="text-brand-400 group-hover:scale-110 transition-transform" />
            <span>Memory Inspector</span>
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-300 border border-brand-500/20 font-mono">
            Rules
          </span>
        </button>
      </div>

      {/* System Status Footer */}
      <div className="p-3 border-t border-dark-800 text-[11px] text-slate-500 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Backend Connected</span>
        </span>
        <span className="font-mono text-[10px] bg-dark-800 px-1.5 py-0.5 rounded text-slate-400">
          v0.1.0
        </span>
      </div>
    </aside>
  );
};
