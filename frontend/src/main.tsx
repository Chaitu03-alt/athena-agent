import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { SessionItem, fetchSessions, createSession, deleteSession } from './api/client';
import { Sidebar } from './components/Sidebar';
import { ChatView } from './views/ChatView';
import { MemoryDrawer } from './components/MemoryDrawer';

function App() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isMemoryDrawerOpen, setIsMemoryDrawerOpen] = useState(false);

  const loadSessions = async () => {
    try {
      const data = await fetchSessions();
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        setActiveSessionId(data[0].id);
      } else if (data.length === 0) {
        // Auto-create initial session if empty
        const newSess = await createSession('Welcome Session');
        setSessions([newSess]);
        setActiveSessionId(newSess.id);
      }
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleNewChat = async () => {
    try {
      const newSession = await createSession(`Chat ${sessions.length + 1}`);
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
    } catch (err) {
      console.error('Failed to create new chat:', err);
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteSession(id);
      const remaining = sessions.filter((s) => s.id !== id);
      setSessions(remaining);
      if (activeSessionId === id) {
        setActiveSessionId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleSessionUpdated = (updatedSession: SessionItem) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === updatedSession.id ? updatedSession : s))
    );
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;

  return (
    <div className="flex h-screen w-screen bg-dark-950 text-slate-100 overflow-hidden font-sans">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onOpenMemoryDrawer={() => setIsMemoryDrawerOpen(true)}
      />
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden">
        <ChatView
          activeSession={activeSession}
          onSessionUpdated={handleSessionUpdated}
          onOpenMemoryDrawer={() => setIsMemoryDrawerOpen(true)}
        />
      </main>
      <MemoryDrawer
        isOpen={isMemoryDrawerOpen}
        onClose={() => setIsMemoryDrawerOpen(false)}
      />
    </div>
  );
}

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
