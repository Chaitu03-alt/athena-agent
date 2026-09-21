import React, { useState, useRef, useEffect } from 'react';
import { audio } from '../utils/audio';

interface CommandInputProps {
  onExecute: (cmd: string) => void;
  disabled?: boolean;
}

const QUICK_COMMANDS = [
  { label: '/status', cmd: '/status' },
  { label: '/rules', cmd: 'list all active procedural rules' },
  { label: '/soul', cmd: 'show current soul profile' },
  { label: '/cron', cmd: 'list scheduled cron jobs' },
  { label: '/clear', cmd: '/clear' },
];

export const CommandInput: React.FC<CommandInputProps> = ({ onExecute, disabled }) => {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, [disabled]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    audio.play('keystroke');

    if (e.key === 'Enter' && input.trim() && !disabled) {
      const trimmed = input.trim();
      audio.play('submit');
      onExecute(trimmed);
      setHistory((prev) => [trimmed, ...prev]);
      setHistoryIdx(-1);
      setInput('');
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (historyIdx < history.length - 1) {
        const nextIdx = historyIdx + 1;
        setHistoryIdx(nextIdx);
        setInput(history[nextIdx]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx > 0) {
        const nextIdx = historyIdx - 1;
        setHistoryIdx(nextIdx);
        setInput(history[nextIdx]);
      } else if (historyIdx === 0) {
        setHistoryIdx(-1);
        setInput('');
      }
    }
  };

  const handleQuickCmd = (cmd: string) => {
    audio.play('keystroke');
    if (cmd === '/clear') {
      onExecute('/clear');
      return;
    }
    setInput(cmd);
    inputRef.current?.focus();
  };

  return (
    <div className="flex flex-col border-t border-[#00ff66]/30 bg-[#0d0d12] p-2.5 gap-2 select-none">
      {/* Quick Suggestion Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto text-[10px] text-[#6f9c82] pb-0.5">
        <span className="text-[#00ff66]/60 font-semibold select-none">QUICK:</span>
        {QUICK_COMMANDS.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => handleQuickCmd(item.cmd)}
            className="px-1.5 py-0.5 border border-[#00ff66]/20 bg-[#060608] hover:border-[#00ff66]/60 hover:text-[#00ff66] text-[10px] rounded-sm transition-colors cursor-pointer"
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Interactive Command Input Line */}
      <div className="flex items-center gap-2 bg-[#060608] border border-[#00ff66]/40 px-3 py-2 shadow-[inset_0_0_10px_rgba(0,0,0,0.8)] focus-within:border-[#00ff66] focus-within:shadow-[0_0_8px_rgba(0,255,102,0.3)] transition-all">
        <span className="text-[#00ff66] font-bold tracking-tight text-xs glow-green-text shrink-0">
          athena&gt;
        </span>
        <div className="relative flex-1 flex items-center">
          <input
            ref={inputRef}
            type="text"
            value={input}
            disabled={disabled}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? 'ATHENA IS PROCESSING TURN...' : 'Enter command, prompt, or tool query...'}
            className="w-full bg-transparent text-[#e0f8e9] font-mono text-xs focus:outline-none placeholder:text-[#6f9c82]/50 tracking-wide"
          />
          {!disabled && (
            <span className="text-[#00ff66] font-bold cursor-blink select-none text-xs ml-0.5 pointer-events-none">
              ▍
            </span>
          )}
        </div>

        <button
          type="button"
          disabled={disabled || !input.trim()}
          onClick={() => {
            if (input.trim() && !disabled) {
              const trimmed = input.trim();
              audio.play('submit');
              onExecute(trimmed);
              setHistory((prev) => [trimmed, ...prev]);
              setHistoryIdx(-1);
              setInput('');
            }
          }}
          className={`px-2.5 py-1 text-[10px] font-bold border transition-all cursor-pointer ${
            input.trim() && !disabled
              ? 'border-[#00ff66] bg-[#00ff66]/20 text-[#00ff66] hover:bg-[#00ff66]/30 shadow-[0_0_5px_rgba(0,255,102,0.4)]'
              : 'border-[#6f9c82]/20 text-[#6f9c82]/40 cursor-not-allowed'
          }`}
        >
          EXECUTE ↵
        </button>
      </div>
    </div>
  );
};
