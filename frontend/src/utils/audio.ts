// Web Audio API Synthesizer for Cyberpunk Operator HUD

type SoundType = 'keystroke' | 'submit' | 'tool_start' | 'tool_end' | 'error' | 'bell';

class AudioManager {
  private ctx: AudioContext | null = null;
  private muted: boolean = false;

  constructor() {
    this.muted = localStorage.getItem('athena_audio_muted') === 'true';
  }

  private initContext() {
    if (!this.ctx && typeof window !== 'undefined') {
      const AudioCtxClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtxClass) {
        this.ctx = new AudioCtxClass();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  public isMuted(): boolean {
    return this.muted;
  }

  public setMuted(muted: boolean): void {
    this.muted = muted;
    localStorage.setItem('athena_audio_muted', String(muted));
  }

  public toggleMute(): boolean {
    this.setMuted(!this.muted);
    return this.muted;
  }

  public play(type: SoundType): void {
    if (this.muted) return;
    try {
      this.initContext();
      if (!this.ctx) return;

      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);

      switch (type) {
        case 'keystroke': {
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(1400, now);
          osc.frequency.exponentialRampToValueAtTime(800, now + 0.015);
          gain.gain.setValueAtTime(0.015, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.015);
          osc.start(now);
          osc.stop(now + 0.015);
          break;
        }
        case 'submit': {
          osc.type = 'square';
          osc.frequency.setValueAtTime(620, now);
          osc.frequency.exponentialRampToValueAtTime(1180, now + 0.06);
          gain.gain.setValueAtTime(0.06, now);
          gain.gain.exponentialRampToValueAtTime(0.005, now + 0.06);
          osc.start(now);
          osc.stop(now + 0.06);
          break;
        }
        case 'tool_start': {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(520, now);
          osc.frequency.exponentialRampToValueAtTime(920, now + 0.08);
          gain.gain.setValueAtTime(0.08, now);
          gain.gain.exponentialRampToValueAtTime(0.005, now + 0.08);
          osc.start(now);
          osc.stop(now + 0.08);
          break;
        }
        case 'tool_end': {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(880, now);
          osc.frequency.exponentialRampToValueAtTime(1360, now + 0.09);
          gain.gain.setValueAtTime(0.07, now);
          gain.gain.exponentialRampToValueAtTime(0.005, now + 0.09);
          osc.start(now);
          osc.stop(now + 0.09);
          break;
        }
        case 'error': {
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(260, now);
          osc.frequency.exponentialRampToValueAtTime(110, now + 0.16);
          gain.gain.setValueAtTime(0.08, now);
          gain.gain.exponentialRampToValueAtTime(0.005, now + 0.16);
          osc.start(now);
          osc.stop(now + 0.16);
          break;
        }
        case 'bell': {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(1200, now);
          gain.gain.setValueAtTime(0.05, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
          osc.start(now);
          osc.stop(now + 0.25);
          break;
        }
      }
    } catch {
      // Audio autoplay policy or device error
    }
  }
}

export const audio = new AudioManager();
