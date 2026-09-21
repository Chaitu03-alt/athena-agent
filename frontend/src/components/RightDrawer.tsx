import React, { useState, useEffect } from 'react';
import { audio } from '../utils/audio';

interface CronJob {
  apscheduler_job_id: string;
  job_type: 'alert' | 'agent_task' | string;
  label: string;
  schedule_desc: string;
  payload?: any;
  created_at?: string;
  last_run_at?: string;
  next_run_at?: string;
}

interface RightDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const RightDrawer: React.FC<RightDrawerProps> = ({ isOpen, onClose }) => {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // New Cron Form
  const [jobType, setJobType] = useState<'alert' | 'agent_task'>('alert');
  const [label, setLabel] = useState('');
  const [scheduleDesc, setScheduleDesc] = useState('*/15 * * * *');
  const [messageOrPrompt, setMessageOrPrompt] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/cron/list');
      const data = await res.json();
      setJobs(Array.isArray(data) ? data : []);
    } catch {
      // Offline fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchJobs();
      const timer = setInterval(fetchJobs, 6000);
      return () => clearInterval(timer);
    }
  }, [isOpen]);

  const handleCreateJob = async () => {
    if (!label.trim() || !scheduleDesc.trim() || !messageOrPrompt.trim()) {
      setFormError('All fields required.');
      return;
    }
    audio.play('submit');
    setFormError(null);
    try {
      const res = await fetch('/api/cron/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_type: jobType,
          label: label.trim(),
          schedule_desc: scheduleDesc.trim(),
          message_or_prompt: messageOrPrompt.trim(),
        }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        audio.play('tool_end');
        setLabel('');
        setMessageOrPrompt('');
        setIsCreating(false);
        fetchJobs();
      } else {
        audio.play('error');
        setFormError(data.message || 'Creation failed');
      }
    } catch (e: any) {
      audio.play('error');
      setFormError(e.message || 'Request failed');
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    audio.play('tool_start');
    try {
      const res = await fetch('/api/cron/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        audio.play('tool_end');
        fetchJobs();
      } else {
        audio.play('error');
      }
    } catch {
      audio.play('error');
    }
  };

  return (
    <aside
      className={`hud-drawer hud-drawer-right ${
        isOpen ? 'w-[280px]' : 'w-0'
      }`}
      style={{ minWidth: isOpen ? '280px' : '0px' }}
    >
      {/* Drawer Header */}
      <div className="p-3 border-b border-[#00ff66]/20 flex items-center justify-between bg-[#101014]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#00f0ff]" />
          <span className="text-xs font-bold tracking-wider text-cyan-400">
            SCHEDULER & CRON
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

      {/* Heartbeat Status Bar */}
      <div className="p-2.5 bg-[#0a0a0a] border-b border-[#00ff66]/15 flex items-center justify-between text-[10px] font-mono">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#00ff66] animate-ping" />
          <span className="text-[#6f9c82]">APScheduler Engine</span>
        </div>
        <span className="text-[#00ff66] font-bold">SQLITE STORE</span>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3 text-xs font-mono">
        {/* Create Job Button / Form */}
        {isCreating ? (
          <div className="p-2.5 border border-cyan-400/40 bg-[#0c0c14] flex flex-col gap-2">
            <div className="text-[10px] text-cyan-400 font-bold flex justify-between items-center">
              <span>SCHEDULE AUTONOMOUS JOB</span>
              <button
                onClick={() => setIsCreating(false)}
                className="text-[#6f9c82] hover:text-white"
              >
                ✕
              </button>
            </div>

            {/* Type selector */}
            <div className="flex gap-1 text-[10px]">
              <button
                type="button"
                onClick={() => setJobType('alert')}
                className={`flex-1 py-1 border text-center cursor-pointer ${
                  jobType === 'alert'
                    ? 'border-amber-400 bg-amber-400/20 text-amber-300 font-bold'
                    : 'border-[#6f9c82]/30 text-[#6f9c82]'
                }`}
              >
                ALERT
              </button>
              <button
                type="button"
                onClick={() => setJobType('agent_task')}
                className={`flex-1 py-1 border text-center cursor-pointer ${
                  jobType === 'agent_task'
                    ? 'border-cyan-400 bg-cyan-400/20 text-cyan-300 font-bold'
                    : 'border-[#6f9c82]/30 text-[#6f9c82]'
                }`}
              >
                AGENT TASK
              </button>
            </div>

            <input
              type="text"
              placeholder="Label (e.g. Daily Reflection)"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="bg-[#060608] border border-[#00ff66]/30 text-xs p-1.5 text-[#e0f8e9]"
            />

            <input
              type="text"
              placeholder="Cron (e.g. 0 9 * * * or */30 * * * *)"
              value={scheduleDesc}
              onChange={(e) => setScheduleDesc(e.target.value)}
              className="bg-[#060608] border border-[#00ff66]/30 text-xs p-1.5 text-[#e0f8e9]"
            />

            <textarea
              placeholder={
                jobType === 'alert'
                  ? 'Notification text to send...'
                  : 'Task instructions for the agent turn loop...'
              }
              value={messageOrPrompt}
              onChange={(e) => setMessageOrPrompt(e.target.value)}
              className="bg-[#060608] border border-[#00ff66]/30 text-xs p-1.5 text-[#e0f8e9] h-16 resize-none"
            />

            {formError && (
              <div className="text-[10px] text-[#ff3366]">{formError}</div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleCreateJob}
                className="flex-1 py-1.5 bg-cyan-400/20 border border-cyan-400 text-cyan-400 font-bold text-xs hover:bg-cyan-400/30 cursor-pointer"
              >
                REGISTER SCHEDULE
              </button>
              <button
                onClick={() => setIsCreating(false)}
                className="px-2 py-1.5 border border-[#6f9c82]/40 text-[#6f9c82] text-xs cursor-pointer"
              >
                CANCEL
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => { setIsCreating(true); audio.play('keystroke'); }}
            className="py-1.5 text-xs border border-dashed border-cyan-400/50 text-cyan-400 hover:bg-cyan-400/10 text-center cursor-pointer tracking-wider"
          >
            + NEW CRON SCHEDULE
          </button>
        )}

        {/* Jobs List */}
        <div className="flex flex-col gap-2">
          <div className="text-[10px] text-[#6f9c82] flex justify-between items-center">
            <span>ACTIVE JOBS ({jobs.length})</span>
            <button
              onClick={() => { fetchJobs(); audio.play('keystroke'); }}
              className="hover:text-[#00ff66]"
              title="Refresh jobs"
            >
              ⟳ REFRESH
            </button>
          </div>

          {jobs.length === 0 ? (
            <div className="text-center py-6 text-[#6f9c82] opacity-70">
              {loading ? 'SYNCING JOBS...' : 'NO ACTIVE CRON JOBS'}
            </div>
          ) : (
            jobs.map((job) => (
              <div
                key={job.apscheduler_job_id}
                className="p-2.5 border border-[#00ff66]/20 bg-[#0a0a0e] hover:border-[#00ff66]/40 transition-all flex flex-col gap-1.5"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-[9px] px-1 py-0.2 border uppercase font-bold ${
                      job.job_type === 'alert'
                        ? 'border-amber-400 text-amber-400 bg-amber-400/10'
                        : 'border-cyan-400 text-cyan-400 bg-cyan-400/10'
                    }`}
                  >
                    {job.job_type}
                  </span>
                  <button
                    onClick={() => handleDeleteJob(job.apscheduler_job_id)}
                    className="text-[#ff3366] hover:text-red-400 text-xs px-1 cursor-pointer"
                    title="Delete Job"
                  >
                    [✕]
                  </button>
                </div>

                <div className="text-xs text-[#e0f8e9] font-bold">
                  {job.label}
                </div>

                <div className="flex items-center justify-between text-[10px] text-[#6f9c82]">
                  <span>CRON: <code className="text-[#00ff66]">{job.schedule_desc}</code></span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
};
