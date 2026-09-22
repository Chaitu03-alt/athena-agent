import React, { useState, useEffect } from 'react';
import { audio } from '../utils/audio';

interface LeftDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LeftDrawer: React.FC<LeftDrawerProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'soul' | 'kv'>('soul');
  
  // Soul State
  const [soulPrompt, setSoulPrompt] = useState('');
  const [originalSoul, setOriginalSoul] = useState('');
  const [soulSaving, setSoulSaving] = useState(false);
  const [soulStatus, setSoulStatus] = useState<string | null>(null);

  // KV State
  const [kvData, setKvData] = useState<Record<string, any>>({});
  const [kvSearch, setKvSearch] = useState('');
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [isAddingKv, setIsAddingKv] = useState(false);

  // Fetch Soul
  const fetchSoul = async () => {
    try {
      const res = await fetch('/api/memory/soul');
      const data = await res.json();
      const rawPrompt = data.prompt;
      const prompt = typeof rawPrompt === 'object' && rawPrompt ? rawPrompt.prompt_text || '' : String(rawPrompt || '');
      setSoulPrompt(prompt);
      setOriginalSoul(prompt);
    } catch {
      // Offline fallback
    }
  };

  // Fetch KV Store
  const fetchKv = async () => {
    try {
      const res = await fetch('/api/memory/kv');
      const data = await res.json();
      setKvData(data || {});
    } catch {
      // Offline fallback
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchSoul();
      fetchKv();
    }
  }, [isOpen]);

  const handleSaveSoul = async () => {
    if (!soulPrompt.trim()) return;
    setSoulSaving(true);
    audio.play('tool_start');
    try {
      const res = await fetch('/api/memory/soul', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt_text: soulPrompt }),
      });
      if (res.ok) {
        audio.play('tool_end');
        setOriginalSoul(soulPrompt);
        setSoulStatus('PROMPT VERSIONED & ACTIVE');
        setTimeout(() => setSoulStatus(null), 3500);
      } else {
        audio.play('error');
        setSoulStatus('ERROR SAVING PROMPT');
      }
    } catch {
      audio.play('error');
      setSoulStatus('NETWORK FAILED');
    } finally {
      setSoulSaving(false);
    }
  };

  const handleSaveKv = async () => {
    if (!newKey.trim() || !newValue.trim()) return;
    audio.play('submit');
    try {
      let parsedVal: any = newValue;
      try {
        parsedVal = JSON.parse(newValue);
      } catch {
        parsedVal = { value: newValue };
      }

      await fetch(`/api/memory/kv/${encodeURIComponent(newKey.trim())}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: parsedVal }),
      });
      audio.play('tool_end');
      setNewKey('');
      setNewValue('');
      setIsAddingKv(false);
      fetchKv();
    } catch {
      audio.play('error');
    }
  };

  const filteredKvKeys = Object.keys(kvData).filter((k) =>
    k.toLowerCase().includes(kvSearch.toLowerCase())
  );

  return (
    <aside
      className={`hud-drawer hud-drawer-left ${
        isOpen ? 'w-[280px]' : 'w-0'
      }`}
      style={{ minWidth: isOpen ? '280px' : '0px' }}
    >
      {/* Drawer Header */}
      <div className="p-3 border-b border-[#00ff66]/20 flex items-center justify-between bg-[#101014]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 bg-[#00ff66] inline-block shadow-[0_0_5px_#00ff66]" />
          <span className="text-xs font-bold tracking-wider text-[#00ff66]">
            MEMORY CORE
          </span>
        </div>
        <button
          onClick={() => { audio.play('keystroke'); onClose(); }}
          className="text-[#6f9c82] hover:text-[#00ff66] text-xs px-1 cursor-pointer"
          title="Close drawer"
        >
          [✕]
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#00ff66]/20 bg-[#0a0a0a] text-xs">
        <button
          onClick={() => { audio.play('keystroke'); setActiveTab('soul'); }}
          className={`flex-1 py-2 text-center transition-colors cursor-pointer border-r border-[#00ff66]/15 ${
            activeTab === 'soul'
              ? 'text-[#00ff66] bg-[#101014] font-bold border-b-2 border-b-[#00ff66]'
              : 'text-[#6f9c82] hover:text-[#00ff66]/80'
          }`}
        >
          SOUL PROFILE
        </button>
        <button
          onClick={() => { audio.play('keystroke'); setActiveTab('kv'); }}
          className={`flex-1 py-2 text-center transition-colors cursor-pointer ${
            activeTab === 'kv'
              ? 'text-[#00ff66] bg-[#101014] font-bold border-b-2 border-b-[#00ff66]'
              : 'text-[#6f9c82] hover:text-[#00ff66]/80'
          }`}
        >
          KV STORE ({Object.keys(kvData).length})
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col text-xs font-mono">
        {activeTab === 'soul' ? (
          <div className="flex flex-col h-full gap-2">
            <div className="flex items-center justify-between text-[10px] text-[#6f9c82]">
              <span>ACTIVE SYSTEM PROMPT</span>
              <span>{soulPrompt.length} CHARS</span>
            </div>

            <textarea
              className="flex-1 w-full bg-[#060608] border border-[#00ff66]/30 text-[#e0f8e9] p-2 text-xs font-mono resize-none focus:outline-none focus:border-[#00ff66] focus:shadow-[0_0_8px_rgba(0,255,102,0.25)] leading-relaxed"
              value={soulPrompt}
              onChange={(e) => setSoulPrompt(e.target.value)}
              placeholder="Configure autonomous persona & directives..."
            />

            {soulStatus && (
              <div className="text-[10px] text-center text-[#00ff66] bg-[#00ff66]/10 py-1 border border-[#00ff66]/30">
                {soulStatus}
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleSaveSoul}
                disabled={soulSaving || soulPrompt === originalSoul}
                className={`flex-1 py-1.5 border text-xs font-bold transition-all cursor-pointer ${
                  soulPrompt !== originalSoul
                    ? 'border-[#00ff66] bg-[#00ff66]/20 text-[#00ff66] hover:bg-[#00ff66]/30 shadow-[0_0_6px_rgba(0,255,102,0.3)]'
                    : 'border-[#6f9c82]/30 text-[#6f9c82]/50 cursor-not-allowed'
                }`}
              >
                {soulSaving ? 'COMMITTING...' : 'SAVE & VERSION'}
              </button>
              <button
                onClick={() => { setSoulPrompt(originalSoul); audio.play('keystroke'); }}
                disabled={soulPrompt === originalSoul}
                className="px-2 py-1.5 border border-[#6f9c82]/30 text-[#6f9c82] hover:text-[#e0f8e9] cursor-pointer"
                title="Revert changes"
              >
                RESET
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col h-full gap-3">
            {/* Search Input */}
            <div className="flex items-center gap-1.5 border border-[#00ff66]/30 bg-[#060608] px-2 py-1">
              <span className="text-[#00ff66] text-[10px]">⌕</span>
              <input
                type="text"
                placeholder="Filter memory keys..."
                value={kvSearch}
                onChange={(e) => setKvSearch(e.target.value)}
                className="bg-transparent border-none text-xs text-[#e0f8e9] focus:outline-none w-full"
              />
              {kvSearch && (
                <button
                  onClick={() => setKvSearch('')}
                  className="text-[#6f9c82] hover:text-[#00ff66] text-[10px]"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Add Key Form */}
            {isAddingKv ? (
              <div className="p-2 border border-[#00ff66]/40 bg-[#0c0c10] flex flex-col gap-2">
                <div className="text-[10px] text-[#00ff66] font-bold">SET NEW MEMORY KEY</div>
                <input
                  type="text"
                  placeholder="key (e.g. user_framework)"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  className="bg-[#060608] border border-[#00ff66]/30 text-xs p-1 text-[#e0f8e9]"
                />
                <textarea
                  placeholder='value (JSON or string)'
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  className="bg-[#060608] border border-[#00ff66]/30 text-xs p-1 text-[#e0f8e9] h-14 resize-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleSaveKv}
                    className="flex-1 py-1 bg-[#00ff66]/20 border border-[#00ff66] text-[#00ff66] text-[11px] font-bold hover:bg-[#00ff66]/30"
                  >
                    COMMIT
                  </button>
                  <button
                    onClick={() => setIsAddingKv(false)}
                    className="px-2 py-1 border border-[#6f9c82]/40 text-[#6f9c82] text-[11px]"
                  >
                    CANCEL
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => { setIsAddingKv(true); audio.play('keystroke'); }}
                className="py-1 text-[11px] border border-dashed border-[#00ff66]/40 text-[#00ff66] hover:bg-[#00ff66]/10 text-center cursor-pointer"
              >
                + SET MEMORY KEY
              </button>
            )}

            {/* KV Item Cards */}
            <div className="flex-1 overflow-y-auto flex flex-col gap-2 pr-1">
              {filteredKvKeys.length === 0 ? (
                <div className="text-center py-6 text-[#6f9c82] opacity-70">
                  NO KV RECORDS FOUND
                </div>
              ) : (
                filteredKvKeys.map((key) => (
                  <div
                    key={key}
                    className="p-2 border border-[#00ff66]/20 bg-[#0a0a0e] hover:border-[#00ff66]/40 transition-colors"
                  >
                    <div className="flex justify-between items-center text-[#00ff66] font-bold text-[11px] mb-1">
                      <span className="truncate">{key}</span>
                    </div>
                    <pre className="text-[10px] text-[#6f9c82] whitespace-pre-wrap break-all bg-[#060608] p-1 border border-[#00ff66]/10 max-h-24 overflow-y-auto">
                      {typeof kvData[key] === 'object'
                        ? JSON.stringify(kvData[key], null, 2)
                        : String(kvData[key])}
                    </pre>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
