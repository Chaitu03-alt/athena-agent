import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Bot, User, Check, Copy, Brain } from 'lucide-react';
import { ChatMessage as ChatMessageType } from '../api/client';

interface Props {
  message: ChatMessageType;
}

export const ChatMessage: React.FC<Props> = ({ message }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`flex w-full py-4 px-4 md:px-6 transition-colors ${
        isUser ? 'justify-end' : 'justify-start bg-dark-900/40 border-y border-dark-800/40'
      }`}
    >
      <div className={`flex max-w-3xl gap-4 ${isUser ? 'flex-row-reverse max-w-xl' : 'w-full'}`}>
        {/* Avatar Icon */}
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold ${
            isUser
              ? 'bg-brand-600 text-white shadow-md shadow-brand-500/20'
              : 'bg-dark-800 text-indigo-400 border border-dark-700'
          }`}
        >
          {isUser ? <User size={16} /> : <Bot size={16} />}
        </div>

        {/* Message Body */}
        <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : 'text-left'}`}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-slate-400">
              {isUser ? 'You' : 'Personal Agent'}
            </span>
            <span className="text-[11px] text-slate-500">
              {message.created_at ? new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
            </span>
          </div>

          <div
            className={`text-sm rounded-xl ${
              isUser
                ? 'inline-block bg-brand-600 text-white px-4 py-2.5 rounded-tr-sm shadow-sm'
                : 'text-slate-200 prose-custom leading-relaxed'
            }`}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div>
                <ReactMarkdown
                  components={{
                    code({ node, className, children, ...props }) {
                      const codeContent = String(children).replace(/\n$/, '');
                      const match = /language-(\w+)/.exec(className || '');
                      const isInline = !match && !codeContent.includes('\n');

                      if (isInline) {
                        return <code className={className} {...props}>{children}</code>;
                      }

                      return (
                        <div className="relative group my-3 rounded-lg overflow-hidden border border-dark-700 bg-dark-950">
                          <div className="flex items-center justify-between px-3 py-1.5 bg-dark-900 border-b border-dark-800 text-[11px] text-slate-400 font-mono">
                            <span>{match ? match[1] : 'code'}</span>
                            <button
                              onClick={() => copyToClipboard(codeContent)}
                              className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors"
                              title="Copy code"
                            >
                              {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                              <span>{copied ? 'Copied' : 'Copy'}</span>
                            </button>
                          </div>
                          <pre className="p-3 text-xs overflow-x-auto font-mono text-slate-200">
                            <code>{children}</code>
                          </pre>
                        </div>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {message.isStreaming && <span className="cursor-blink" />}
              </div>
            )}
          </div>

          {/* Episodic Memory Info Badge if available */}
          {!isUser && message.importance_score !== undefined && (
            <div className="flex items-center gap-2 mt-2 pt-1">
              <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-dark-850 border border-dark-700 text-slate-400">
                <Brain size={11} className="text-indigo-400" />
                <span>Episodic Log</span>
                <span className="text-indigo-300 font-mono">
                  {message.importance_score.toFixed(2)}
                </span>
                {message.tags && message.tags.length > 0 && (
                  <span className="text-slate-500 border-l border-dark-700 pl-1.5">
                    {message.tags.slice(0, 3).join(', ')}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
