import React, { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, Brain, Cpu, MessageSquare } from 'lucide-react';
import {
  ChatMessage as ChatMessageType,
  SessionItem,
  fetchMessages,
  sendMessageStream,
} from '../api/client';
import { ChatMessage } from '../components/ChatMessage';

interface Props {
  activeSession: SessionItem | null;
  onSessionUpdated: (session: SessionItem) => void;
  onOpenMemoryDrawer?: () => void;
}

export const ChatView: React.FC<Props> = ({ activeSession, onSessionUpdated, onOpenMemoryDrawer }) => {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom of conversation
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (!activeSession) {
      setMessages([]);
      return;
    }

    setIsLoading(true);
    fetchMessages(activeSession.id)
      .then((data) => {
        setMessages(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load messages:', err);
        setIsLoading(false);
      });
  }, [activeSession?.id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // Handle textarea auto-resize
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  };

  const handleSend = async (contentToSend?: string) => {
    const text = (contentToSend || input).trim();
    if (!text || !activeSession || isStreaming) return;

    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Append user message optimistically
    const userMsg: ChatMessageType = {
      id: `temp-${Date.now()}`,
      session_id: activeSession.id,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };

    // Placeholder assistant message for streaming
    const assistantMsg: ChatMessageType = {
      id: `temp-assistant-${Date.now()}`,
      session_id: activeSession.id,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    await sendMessageStream(
      activeSession.id,
      text,
      (chunk) => {
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: updated[lastIdx].content + chunk,
            };
          }
          return updated;
        });
      },
      (doneData) => {
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              id: doneData.message_id || updated[lastIdx].id,
              isStreaming: false,
              importance_score: doneData.importance_score,
              tags: doneData.tags,
            };
          }
          return updated;
        });

        if (doneData.session_title && doneData.session_title !== activeSession.title) {
          onSessionUpdated({ ...activeSession, title: doneData.session_title });
        }
      },
      (error) => {
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: updated[lastIdx].content + `\n\n*[Error: ${error}]*`,
              isStreaming: false,
            };
          }
          return updated;
        });
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!activeSession) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-dark-950 p-6 text-center text-slate-400">
        <MessageSquare size={36} className="text-slate-600 mb-3" />
        <h2 className="text-base font-medium text-slate-200">No session selected</h2>
        <p className="text-xs text-slate-500 mt-1">Select a chat from the sidebar or start a new one.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-dark-950 overflow-hidden">
      {/* Top Header Bar */}
      <header className="h-14 border-b border-dark-800 px-6 flex items-center justify-between bg-dark-900/60 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm font-medium text-slate-100 truncate">{activeSession.title}</span>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={onOpenMemoryDrawer}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-brand-600/20 hover:bg-brand-600/30 active:bg-brand-600/40 border border-brand-500/30 text-brand-300 hover:text-white transition-all shadow-sm shadow-brand-500/10 cursor-pointer"
            title="Open Memory Inspector (learned procedural rules & preferences)"
          >
            <Brain size={13} className="text-brand-400" />
            <span>Memory Inspector</span>
          </button>
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-dark-850 border border-dark-700 text-slate-300">
            <Cpu size={12} className="text-indigo-400" />
            <span className="font-mono text-[11px]">claude-sonnet-4-6</span>
          </div>
        </div>
      </header>

      {/* Message Thread */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-xs text-slate-500">
            Loading messages...
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-full py-16 px-4 max-w-xl mx-auto text-center">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 shadow-lg shadow-indigo-500/5">
              <Sparkles size={24} />
            </div>
            <h2 className="text-lg font-semibold text-slate-100 tracking-tight">How can I assist you?</h2>
            <p className="text-xs text-slate-400 mt-1.5 max-w-md">
              Chat turns are automatically evaluated for importance and logged to episodic memory. Try one of these prompts:
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-6 w-full text-left">
              {[
                'Remember that I prefer strict typing in Python and TypeScript.',
                'Explain how Phase 1 episodic memory logging works.',
                'Never use tabs for indentation, always 4 spaces.',
                'Help me design a clean REST API in FastAPI.',
              ].map((promptText, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(promptText)}
                  className="p-3 rounded-lg border border-dark-800 bg-dark-900/60 hover:bg-dark-850 hover:border-dark-700 text-xs text-slate-300 hover:text-white transition-all text-left group"
                >
                  <p className="line-clamp-2">{promptText}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="py-4">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Form */}
      <div className="p-4 border-t border-dark-800 bg-dark-900/50 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end bg-dark-950 border border-dark-700 focus-within:border-brand-500 rounded-xl p-2 transition-colors shadow-inner">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Enter to send, Shift+Enter for newline)"
              className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 resize-none outline-none py-1.5 px-2 max-h-44 min-h-[36px]"
              disabled={isStreaming}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isStreaming}
              className={`flex-shrink-0 p-2 rounded-lg transition-all ${
                input.trim() && !isStreaming
                  ? 'bg-brand-600 text-white hover:bg-brand-500 active:bg-brand-700 shadow-sm shadow-brand-500/30'
                  : 'bg-dark-800 text-slate-600 cursor-not-allowed'
              }`}
              title="Send message"
            >
              <Send size={15} />
            </button>
          </div>
          <div className="flex justify-between items-center text-[11px] text-slate-500 mt-2 px-1">
            <span>Adaptive AI Agent • Multi-turn Chat Loop</span>
            <span className="hidden sm:inline">Press Enter to send</span>
          </div>
        </div>
      </div>
    </div>
  );
};
