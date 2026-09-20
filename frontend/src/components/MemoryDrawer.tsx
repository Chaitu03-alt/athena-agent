import React, { useState, useEffect, useMemo } from 'react';
import {
  X,
  RefreshCw,
  Brain,
  Code2,
  GitBranch,
  Lightbulb,
  Trash2,
  CheckCircle2,
  Search,
  Clock,
  Layers,
  Shield,
  FileQuestion,
  Wrench,
} from 'lucide-react';
import {
  MemoryRule,
  fetchMemoryRules,
  updateRuleStatus,
  deleteMemoryRule,
  triggerConsolidation,
} from '../api/client';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onRulesChanged?: (rules: MemoryRule[]) => void;
}

export const MemoryDrawer: React.FC<Props> = ({ isOpen, onClose, onRulesChanged }) => {
  const [rules, setRules] = useState<MemoryRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeOnly, setActiveOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [isConsolidating, setIsConsolidating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  // Load rules when drawer opens or activeOnly changes
  const loadRules = async () => {
    setLoading(true);
    try {
      const data = await fetchMemoryRules(activeOnly);
      setRules(data);
      if (onRulesChanged) {
        onRulesChanged(data);
      }
    } catch (err: any) {
      console.error('Failed to load memory rules:', err);
      setStatusMessage({ type: 'error', text: 'Failed to load rules: ' + (err.message || 'Unknown error') });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadRules();
    }
  }, [isOpen, activeOnly]);

  // Dismiss drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Trigger immediate memory consolidation
  const handleConsolidateNow = async () => {
    setIsConsolidating(true);
    setStatusMessage(null);
    try {
      const res = await triggerConsolidation(0.5);
      setStatusMessage({
        type: 'success',
        text: `Consolidation complete: ${res.procedural_created_count} new procedural rule(s), ${res.semantic_created_count} facts learned.`,
      });
      await loadRules();
    } catch (err: any) {
      console.error('Consolidation failed:', err);
      setStatusMessage({
        type: 'error',
        text: 'Consolidation failed: ' + (err.message || 'Server error'),
      });
    } finally {
      setIsConsolidating(false);
      setTimeout(() => setStatusMessage(null), 5000);
    }
  };

  // Toggle active / inactive switch for a rule
  const handleToggleRule = async (rule: MemoryRule) => {
    const newStatus = !rule.is_active;
    setTogglingIds((prev) => new Set(prev).add(rule.id));

    // Optimistic UI update
    setRules((prev) =>
      prev.map((r) => (r.id === rule.id ? { ...r, is_active: newStatus, active: newStatus } : r))
    );

    try {
      const updated = await updateRuleStatus(rule.id, newStatus);
      setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)));
      if (onRulesChanged) {
        onRulesChanged(rules.map((r) => (r.id === rule.id ? updated : r)));
      }
    } catch (err: any) {
      console.error('Failed to update rule:', err);
      // Revert optimistic update
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, is_active: rule.is_active, active: rule.is_active } : r))
      );
      setStatusMessage({ type: 'error', text: `Failed to toggle rule: ${err.message}` });
    } finally {
      setTogglingIds((prev) => {
        const next = new Set(prev);
        next.delete(rule.id);
        return next;
      });
    }
  };

  // Delete / archive rule
  const handleDeleteRule = async (ruleId: string) => {
    setDeletingIds((prev) => new Set(prev).add(ruleId));
    try {
      await deleteMemoryRule(ruleId);
      // If we are in activeOnly mode, remove from view; else mark as inactive
      if (activeOnly) {
        setRules((prev) => prev.filter((r) => r.id !== ruleId));
      } else {
        setRules((prev) =>
          prev.map((r) => (r.id === ruleId ? { ...r, is_active: false, active: false } : r))
        );
      }
      setStatusMessage({ type: 'success', text: 'Rule archived successfully.' });
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err: any) {
      console.error('Failed to delete rule:', err);
      setStatusMessage({ type: 'error', text: `Failed to archive rule: ${err.message}` });
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(ruleId);
        return next;
      });
    }
  };

  // Filter rules based on search and category
  const filteredRules = useMemo(() => {
    return rules.filter((rule) => {
      const matchesSearch =
        rule.rule_statement.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rule.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rule.source.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesCategory =
        selectedCategory === 'all' ||
        rule.category.toLowerCase() === selectedCategory.toLowerCase() ||
        (selectedCategory === 'tool_preference' && (rule.category.toLowerCase().includes('tool') || rule.category.toLowerCase() === 'tool_preference')) ||
        (selectedCategory === 'facts' && rule.category.toLowerCase().includes('fact'));

      return matchesSearch && matchesCategory;
    });
  }, [rules, searchQuery, selectedCategory]);

  // Group rules by category
  const groupedRules = useMemo(() => {
    const groups: Record<string, MemoryRule[]> = {
      coding_style: [],
      workflow: [],
      tool_preference: [],
      facts: [],
      other: [],
    };

    filteredRules.forEach((rule) => {
      const cat = rule.category.toLowerCase();
      if (cat === 'coding_style') {
        groups.coding_style.push(rule);
      } else if (cat === 'workflow') {
        groups.workflow.push(rule);
      } else if (cat === 'tool_preference' || cat === 'tooling') {
        groups.tool_preference.push(rule);
      } else if (cat.includes('fact')) {
        groups.facts.push(rule);
      } else {
        groups.other.push(rule);
      }
    });

    return groups;
  }, [filteredRules]);

  // Helper for category presentation
  const getCategoryMeta = (catKey: string) => {
    switch (catKey) {
      case 'coding_style':
        return {
          label: 'Coding Style',
          icon: <Code2 size={16} className="text-cyan-400" />,
          bgColor: 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400',
        };
      case 'workflow':
        return {
          label: 'Workflow & Habits',
          icon: <GitBranch size={16} className="text-indigo-400" />,
          bgColor: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400',
        };
      case 'tool_preference':
        return {
          label: 'Tool Preferences',
          icon: <Wrench size={16} className="text-amber-400" />,
          bgColor: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
        };
      case 'facts':
        return {
          label: 'Facts & Constraints',
          icon: <Lightbulb size={16} className="text-yellow-400" />,
          bgColor: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400',
        };
      default:
        return {
          label: 'General Rules',
          icon: <Layers size={16} className="text-emerald-400" />,
          bgColor: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
        };
    }
  };

  // Helper for confidence badge colors
  const getConfidenceBadge = (confidence: number) => {
    const pct = Math.round(confidence * 100);
    if (pct >= 90) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 flex items-center gap-1">
          <Shield size={10} />
          <span>{pct}% confidence</span>
        </span>
      );
    } else if (pct >= 75) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-500/10 border border-sky-500/25 text-sky-400 flex items-center gap-1">
          <Shield size={10} />
          <span>{pct}% confidence</span>
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 border border-amber-500/25 text-amber-400 flex items-center gap-1">
        <Shield size={10} />
        <span>{pct}% confidence</span>
      </span>
    );
  };

  // Helper for source badge
  const getSourceBadge = (source: string) => {
    const isExplicit = source === 'explicit_user';
    return (
      <span
        className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
          isExplicit
            ? 'bg-purple-500/10 border-purple-500/25 text-purple-300'
            : 'bg-slate-800 border-slate-700 text-slate-300'
        }`}
      >
        {isExplicit ? 'User Explicit' : 'Consolidation Inferred'}
      </span>
    );
  };

  if (!isOpen) return null;

  const activeCount = rules.filter((r) => r.is_active).length;
  const totalCount = rules.length;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-dark-950/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Slide-out Drawer */}
      <aside className="relative w-full max-w-2xl bg-dark-900 border-l border-dark-800 shadow-2xl flex flex-col h-full z-10 animate-in slide-in-from-right duration-200">
        {/* Drawer Header */}
        <div className="p-5 border-b border-dark-800 bg-dark-900/90 backdrop-blur sticky top-0 z-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-sm shadow-indigo-500/10">
              <Brain size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-slate-100 tracking-tight">Memory Inspector</h2>
                <span className="px-2 py-0.5 text-[11px] font-medium rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                  {activeCount} active
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Inspect, toggle, and manage learned procedural rules & system preferences.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleConsolidateNow}
              disabled={isConsolidating}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                isConsolidating
                  ? 'bg-dark-800 border-dark-700 text-slate-500 cursor-not-allowed'
                  : 'bg-brand-600/20 border-brand-500/30 text-brand-400 hover:bg-brand-600/30 active:bg-brand-600/40 hover:text-white'
              }`}
              title="Consolidate recent episodic memories into procedural rules"
            >
              <RefreshCw size={13} className={isConsolidating ? 'animate-spin text-brand-400' : ''} />
              <span>{isConsolidating ? 'Consolidating...' : 'Consolidate Now'}</span>
            </button>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-800 rounded-lg transition-colors"
              title="Close drawer (Esc)"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Status Notification */}
        {statusMessage && (
          <div
            className={`mx-5 mt-4 p-3 rounded-lg text-xs flex items-center justify-between border animate-in fade-in duration-200 ${
              statusMessage.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            }`}
          >
            <div className="flex items-center gap-2">
              {statusMessage.type === 'success' ? <CheckCircle2 size={14} /> : <FileQuestion size={14} />}
              <span>{statusMessage.text}</span>
            </div>
            <button
              onClick={() => setStatusMessage(null)}
              className="text-slate-400 hover:text-slate-200 text-[11px]"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Toolbar & Filters */}
        <div className="px-5 py-3 border-b border-dark-800/80 bg-dark-950/40 space-y-3">
          {/* Active vs All segmented toggle + Search */}
          <div className="flex flex-col sm:flex-row gap-2.5 items-stretch sm:items-center justify-between">
            {/* Segmented active filter */}
            <div className="inline-flex rounded-lg bg-dark-950 p-1 border border-dark-800">
              <button
                onClick={() => setActiveOnly(false)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                  !activeOnly
                    ? 'bg-dark-800 text-slate-100 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                All ({totalCount})
              </button>
              <button
                onClick={() => setActiveOnly(true)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                  activeOnly
                    ? 'bg-dark-800 text-slate-100 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Active only ({activeCount})
              </button>
            </div>

            {/* Search Input */}
            <div className="relative flex-1 sm:max-w-xs">
              <Search size={13} className="absolute left-2.5 top-2.5 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter rules by text or tag..."
                className="w-full bg-dark-950 border border-dark-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-2 text-slate-500 hover:text-slate-300"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Category Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 text-xs">
            <span className="text-[11px] text-slate-500 uppercase tracking-wider mr-1">Category:</span>
            {[
              { id: 'all', label: 'All' },
              { id: 'coding_style', label: 'Coding Style' },
              { id: 'workflow', label: 'Workflow' },
              { id: 'tool_preference', label: 'Tool Preferences' },
              { id: 'facts', label: 'Facts' },
            ].map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors whitespace-nowrap ${
                  selectedCategory === cat.id
                    ? 'bg-indigo-600 text-white border-indigo-500'
                    : 'bg-dark-900 border-dark-800 text-slate-400 hover:text-slate-200 hover:border-dark-700'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* Rules Content List */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500 text-xs gap-2">
              <RefreshCw size={20} className="animate-spin text-brand-500" />
              <span>Loading memories...</span>
            </div>
          ) : filteredRules.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <div className="w-12 h-12 rounded-2xl bg-dark-800 border border-dark-700 flex items-center justify-center text-slate-500 mb-3">
                <Brain size={22} />
              </div>
              <h3 className="text-sm font-medium text-slate-200">No memory rules found</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm">
                {searchQuery || selectedCategory !== 'all'
                  ? 'Try clearing the search query or category filter.'
                  : 'Start conversing or click "Consolidate Now" to reflect and infer procedural rules from chat history.'}
              </p>
            </div>
          ) : (
            (['coding_style', 'workflow', 'tool_preference', 'facts', 'other'] as const).map((groupKey) => {
              const groupItems = groupedRules[groupKey];
              if (!groupItems || groupItems.length === 0) return null;
              const meta = getCategoryMeta(groupKey);

              return (
                <section key={groupKey} className="space-y-3">
                  {/* Category Header */}
                  <div className="flex items-center justify-between pb-1 border-b border-dark-800">
                    <div className="flex items-center gap-2">
                      {meta.icon}
                      <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                        {meta.label}
                      </h3>
                      <span className="px-1.5 py-0.2 text-[10px] font-mono rounded bg-dark-800 text-slate-400">
                        {groupItems.length}
                      </span>
                    </div>
                  </div>

                  {/* Rule Cards */}
                  <div className="space-y-2.5">
                    {groupItems.map((rule) => {
                      const isToggling = togglingIds.has(rule.id);
                      const isDeleting = deletingIds.has(rule.id);

                      return (
                        <div
                          key={rule.id}
                          className={`p-4 rounded-xl border transition-all ${
                            rule.is_active
                              ? 'bg-dark-850/80 border-dark-700/80 hover:border-dark-600 shadow-sm'
                              : 'bg-dark-950/60 border-dark-800/60 opacity-60 hover:opacity-90'
                          }`}
                        >
                          {/* Top Row: Badges & Controls */}
                          <div className="flex items-start justify-between gap-3 mb-2.5">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {/* Active/Inactive Status Badge */}
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-medium border flex items-center gap-1 ${
                                  rule.is_active
                                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                                    : 'bg-slate-800 border-slate-700 text-slate-400'
                                }`}
                              >
                                <span
                                  className={`w-1.5 h-1.5 rounded-full ${
                                    rule.is_active ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
                                  }`}
                                />
                                {rule.is_active ? 'Active' : 'Archived'}
                              </span>

                              {/* Confidence Badge */}
                              {getConfidenceBadge(rule.confidence)}

                              {/* Version Badge */}
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-dark-800 border border-dark-700 text-indigo-300">
                                v{rule.version}
                              </span>

                              {/* Source Badge */}
                              {getSourceBadge(rule.source)}

                              {/* Archived Reason Badge if decayed/archived */}
                              {rule.archived_reason && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border bg-amber-500/10 border-amber-500/25 text-amber-300">
                                  Archived: {rule.archived_reason}
                                </span>
                              )}
                            </div>

                            {/* Actions: Toggle Switch & Delete */}
                            <div className="flex items-center gap-2 flex-shrink-0">
                              {/* Toggle switch */}
                              <button
                                type="button"
                                role="switch"
                                aria-checked={rule.is_active}
                                disabled={isToggling}
                                onClick={() => handleToggleRule(rule)}
                                title={rule.is_active ? 'Click to disable rule' : 'Click to enable rule'}
                                className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                                  rule.is_active ? 'bg-emerald-500' : 'bg-dark-700'
                                } ${isToggling ? 'opacity-50 cursor-wait' : ''}`}
                              >
                                <span
                                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                    rule.is_active ? 'translate-x-4' : 'translate-x-0'
                                  }`}
                                />
                              </button>

                              {/* Delete button */}
                              <button
                                onClick={() => handleDeleteRule(rule.id)}
                                disabled={isDeleting}
                                className="p-1 text-slate-500 hover:text-rose-400 rounded transition-colors"
                                title="Deactivate / archive rule"
                              >
                                <Trash2 size={14} className={isDeleting ? 'animate-pulse text-rose-400' : ''} />
                              </button>
                            </div>
                          </div>

                          {/* Rule Statement */}
                          <p className="text-xs font-medium text-slate-100 leading-relaxed font-sans">
                            {rule.rule_statement}
                          </p>

                          {/* Footer Info */}
                          <div className="mt-2.5 pt-2 border-t border-dark-800/60 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500 font-mono">
                            <div className="flex items-center gap-3">
                              <span className="flex items-center gap-1">
                                <Clock size={11} />
                                <span>
                                  {rule.last_accessed_at
                                    ? `Accessed ${new Date(rule.last_accessed_at).toLocaleDateString()}`
                                    : rule.updated_at
                                    ? `Updated ${new Date(rule.updated_at).toLocaleDateString()}`
                                    : `Created ${new Date(rule.created_at).toLocaleDateString()}`}
                                </span>
                              </span>
                              <span className="flex items-center gap-1 text-slate-400">
                                <Layers size={11} />
                                <span>{rule.access_count ?? 1}x used</span>
                              </span>
                            </div>
                            <span className="text-[10px] text-slate-600 truncate max-w-[150px]">
                              ID: {rule.id.slice(0, 8)}...
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              );
            })
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-3.5 border-t border-dark-800 bg-dark-950/80 text-[11px] text-slate-500 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Procedural & Semantic RAG Injection: Active</span>
          </div>
          <span className="text-slate-400 font-mono text-[10px]">
            Qdrant Payload Synced
          </span>
        </div>
      </aside>
    </div>
  );
};
