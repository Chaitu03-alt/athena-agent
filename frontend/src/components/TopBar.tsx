import React from 'react';
import { audio } from '../utils/audio';

export interface TelemetryData {
  cpu: number;
  ram: number;
  uptime: number;
  state: 'idle' | 'thinking' | 'calling_tool' | string;
  provider?: string;
  wsStatus: 'connected' | 'reconnecting' | 'disconnected';
}

interface TopBarProps {
  telemetry: TelemetryData;
  scanlines: boolean;
  onToggleScanlines: () => void;
  isMuted: boolean;
  onToggleMute: () => void;
  isVoiceEnabled?: boolean;
  onToggleVoice?: () => void;
  isSpeaking?: boolean;
  leftOpen: boolean;
  onToggleLeft: () => void;
  rightOpen: boolean;
  onToggleRight: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  telemetry,
  scanlines,
  onToggleScanlines,
  isMuted,
  onToggleMute,
  isVoiceEnabled = true,
  onToggleVoice,
  isSpeaking = false,
  leftOpen,
  onToggleLeft,
  rightOpen,
  onToggleRight,
}) => {
  const formatUptime = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getStateColor = (state: string) => {
    switch (state.toLowerCase()) {
      case 'thinking':
        return 'bg-amber-400 text-black shadow-[0_0_8px_rgba(255,184,0,0.8)]';
      case 'calling_tool':
        return 'bg-cyan-400 text-black shadow-[0_0_8px_rgba(0,240,255,0.8)]';
      case 'speaking':
        return 'bg-[#00f0ff] text-black shadow-[0_0_8px_rgba(0,240,255,0.9)]';
      case 'listening':
        return 'bg-rose-400 text-black shadow-[0_0_8px_rgba(251,113,133,0.9)]';
      default:
        return 'bg-[#00ff66] text-black shadow-[0_0_8px_rgba(0,255,102,0.8)]';
    }
  };

  return (
    <header className="hud-topbar select-none">
      {/* Left: Brand & Drawer Toggles */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 font-bold tracking-wider text-[#00ff66] glow-green-text">
          <span className="inline-block w-2.5 h-2.5 bg-[#00ff66] shadow-[0_0_6px_#00ff66]" />
          <span>ATHENA // OPERATOR HUD</span>
          <span className="text-[9px] px-1 py-0.5 border border-[#00ff66]/40 text-[#6f9c82]">v5.0</span>
        </div>

        <div className="hidden sm:flex items-center gap-1.5 ml-2">
          <button
            onClick={() => { audio.play('keystroke'); onToggleLeft(); }}
            className={`px-2 py-0.5 text-[10px] border transition-all cursor-pointer ${
              leftOpen
                ? 'border-[#00ff66] bg-[#00ff66]/15 text-[#00ff66] shadow-[0_0_5px_rgba(0,255,102,0.3)]'
                : 'border-[#6f9c82]/40 text-[#6f9c82] hover:border-[#00ff66]/60 hover:text-[#00ff66]'
            }`}
            title="Toggle Memory & Soul Drawer"
          >
            [SOUL / MEM]
          </button>
          <button
            onClick={() => { audio.play('keystroke'); onToggleRight(); }}
            className={`px-2 py-0.5 text-[10px] border transition-all cursor-pointer ${
              rightOpen
                ? 'border-[#00ff66] bg-[#00ff66]/15 text-[#00ff66] shadow-[0_0_5px_rgba(0,255,102,0.3)]'
                : 'border-[#6f9c82]/40 text-[#6f9c82] hover:border-[#00ff66]/60 hover:text-[#00ff66]'
            }`}
            title="Toggle Cron & Autonomous Tasks Drawer"
          >
            [CRON / RT]
          </button>
        </div>
      </div>

      {/* Center: Live Telemetry Gauges */}
      <div className="hidden lg:flex items-center gap-4 text-[11px] font-mono">
        {/* Agent State */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 border border-[#00ff66]/30 bg-[#101014]">
          <span
            className={`w-2 h-2 rounded-full ${
              telemetry.state !== 'idle' ? 'pulse-fast' : 'animate-pulse'
            } ${getStateColor(telemetry.state)}`}
          />
          <span className="text-[#6f9c82]">STATE:</span>
          <span className="font-bold text-[#e0f8e9]">{telemetry.state.toUpperCase()}</span>
        </div>

        {/* CPU */}
        <div className="flex items-center gap-1">
          <span className="text-[#6f9c82]">CPU:</span>
          <span className="text-[#e0f8e9] font-medium">{telemetry.cpu.toFixed(1)}%</span>
        </div>

        {/* RAM */}
        <div className="flex items-center gap-1">
          <span className="text-[#6f9c82]">RAM:</span>
          <span className="text-[#e0f8e9] font-medium">{telemetry.ram.toFixed(0)}MB</span>
        </div>

        {/* SQLite WAL */}
        <div className="flex items-center gap-1 bg-[#00ff66]/10 px-1.5 py-0.5 border border-[#00ff66]/30 text-[#00ff66]">
          <span>WAL:</span>
          <span className="font-bold">ACTIVE</span>
        </div>

        {/* Uptime */}
        <div className="flex items-center gap-1">
          <span className="text-[#6f9c82]">UPTIME:</span>
          <span className="text-[#e0f8e9]">{formatUptime(telemetry.uptime)}</span>
        </div>
      </div>

      {/* Right: Status & Controls */}
      <div className="flex items-center gap-2 text-[11px]">
        {/* WebSocket Status */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 bg-[#0a0a0a] border border-[#00ff66]/20">
          <span
            className={`w-2 h-2 rounded-full ${
              telemetry.wsStatus === 'connected'
                ? 'bg-[#00ff66] shadow-[0_0_6px_#00ff66]'
                : telemetry.wsStatus === 'reconnecting'
                ? 'bg-amber-400 animate-ping shadow-[0_0_6px_#ffb800]'
                : 'bg-[#ff3366] shadow-[0_0_6px_#ff3366]'
            }`}
          />
          <span className="text-[10px] text-[#6f9c82]">
            {telemetry.wsStatus === 'connected' ? 'WS: LIVE' : telemetry.wsStatus.toUpperCase()}
          </span>
        </div>

        {/* Voice Mode Toggle */}
        <button
          onClick={() => { onToggleVoice?.(); audio.play('keystroke'); }}
          className={`px-2 py-0.5 border text-[10px] cursor-pointer transition-colors flex items-center gap-1.5 ${
            isVoiceEnabled
              ? isSpeaking
                ? 'border-[#00f0ff] bg-[#00f0ff]/20 text-[#00f0ff] animate-pulse shadow-[0_0_8px_rgba(0,240,255,0.7)]'
                : 'border-[#00f0ff]/60 text-[#00f0ff] hover:bg-[#00f0ff]/10 shadow-[0_0_5px_rgba(0,240,255,0.3)]'
              : 'border-[#6f9c82]/30 text-[#6f9c82]/50 hover:border-[#6f9c82]/60'
          }`}
          title="Toggle Athena Voice Mode (Speech Synthesis & Voice Interaction)"
        >
          <span className={`w-1.5 h-1.5 rounded-full ${
            isVoiceEnabled
              ? isSpeaking
                ? 'bg-[#00f0ff] animate-ping'
                : 'bg-[#00f0ff]'
              : 'bg-zinc-600'
          }`} />
          <span>VOICE: {isVoiceEnabled ? 'ON' : 'OFF'}</span>
        </button>

        {/* Sound Toggle */}
        <button
          onClick={() => { onToggleMute(); audio.play('keystroke'); }}
          className={`px-2 py-0.5 border text-[10px] cursor-pointer transition-colors ${
            !isMuted
              ? 'border-[#00ff66]/50 text-[#00ff66] hover:bg-[#00ff66]/10'
              : 'border-[#ff3366]/40 text-[#ff3366] hover:bg-[#ff3366]/10'
          }`}
          title="Toggle Audio Feedback"
        >
          {isMuted ? 'AUDIO: OFF' : 'AUDIO: ON'}
        </button>

        {/* CRT Scanline Toggle */}
        <button
          onClick={() => { audio.play('keystroke'); onToggleScanlines(); }}
          className={`px-2 py-0.5 border text-[10px] cursor-pointer transition-colors ${
            scanlines
              ? 'border-[#00ff66]/50 text-[#00ff66] hover:bg-[#00ff66]/10'
              : 'border-[#6f9c82]/40 text-[#6f9c82] hover:border-[#00ff66]/40'
          }`}
          title="Toggle CRT Scanlines & Flicker"
        >
          CRT: {scanlines ? 'ON' : 'OFF'}
        </button>
      </div>
    </header>
  );
};
