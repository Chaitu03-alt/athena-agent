/**
 * Typed API Client for Personal Adaptive AI Agent.
 */

export interface SessionItem {
  id: string;
  title: string;
  project_id?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  created_at: string;
  importance_score?: number;
  tags?: string[];
  isStreaming?: boolean;
}

const BASE_URL = '/api';

export async function fetchSessions(): Promise<SessionItem[]> {
  const res = await fetch(`${BASE_URL}/sessions`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sessions: ${res.statusText}`);
  }
  return res.json();
}

export async function createSession(title: string = 'New Chat'): Promise<SessionItem> {
  const res = await fetch(`${BASE_URL}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    throw new Error(`Failed to create session: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete session: ${res.statusText}`);
  }
}

export async function fetchMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/messages`);
  if (!res.ok) {
    throw new Error(`Failed to fetch messages: ${res.statusText}`);
  }
  return res.json();
}

export async function sendMessageStream(
  sessionId: string,
  content: string,
  onToken: (chunk: string) => void,
  onDone: (data: { message_id: string; importance_score: number; tags?: string[]; session_title?: string }) => void,
  onError: (error: string) => void
): Promise<void> {
  const response = await fetch(`${BASE_URL}/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    onError(`Server responded with ${response.status}: ${response.statusText}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError('Response body is not readable');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === 'token') {
              onToken(event.content);
            } else if (event.type === 'done') {
              onDone(event);
            } else if (event.type === 'error') {
              onError(event.error);
            }
          } catch {
            // Ignore parse errors on partial chunks
          }
        }
      }
    }
  } catch (err: any) {
    onError(err.message || 'Stream read error');
  }
}

export interface MemoryRule {
  id: string;
  rule_statement: string;
  category: string;
  confidence: number;
  source: string;
  source_episodic_ids?: string[];
  superseded_by?: string | null;
  active?: boolean;
  is_active: boolean;
  version: number;
  last_accessed_at?: string;
  access_count?: number;
  archived_reason?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface ConsolidationResult {
  status: string;
  message: string;
  processed_episodic_count: number;
  procedural_created_count: number;
  semantic_created_count: number;
  memories: any[];
}

export async function fetchMemoryRules(
  activeOnly: boolean = true,
  category?: string
): Promise<MemoryRule[]> {
  const params = new URLSearchParams();
  params.set('active_only', activeOnly ? 'true' : 'false');
  if (category && category !== 'all') {
    params.set('category', category);
  }

  const res = await fetch(`${BASE_URL}/memory/rules?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch memory rules: ${res.statusText}`);
  }
  return res.json();
}

export async function updateRuleStatus(
  ruleId: string,
  isActive: boolean
): Promise<MemoryRule> {
  const res = await fetch(`${BASE_URL}/memory/rules/${ruleId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active: isActive }),
  });
  if (!res.ok) {
    throw new Error(`Failed to update rule status: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteMemoryRule(ruleId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/memory/rules/${ruleId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete memory rule: ${res.statusText}`);
  }
}

export async function triggerConsolidation(
  importanceThreshold: number = 0.5
): Promise<ConsolidationResult> {
  const res = await fetch(`${BASE_URL}/memory/consolidate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ importance_threshold: importanceThreshold }),
  });
  if (!res.ok) {
    throw new Error(`Failed to trigger consolidation: ${res.statusText}`);
  }
  return res.json();
}

