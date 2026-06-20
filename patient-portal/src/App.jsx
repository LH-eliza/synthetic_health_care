import { useCallback, useEffect, useState } from 'react';
import { fetchPortalData, sendToDoctor } from './api';
import ProgressHeader from './components/ProgressHeader';
import DoctorCard from './components/DoctorCard';
import VisitSummary from './components/VisitSummary';
import TaskSection from './components/TaskSection';
import TipsSection from './components/TipsSection';
import DownloadReport from './components/DownloadReport';
import ProgressCalendar from './components/ProgressCalendar';
import ConfirmationView from './components/ConfirmationView';
import CollapsibleSection from './components/CollapsibleSection';
import { isTaskCompleteForProgress } from './utils/taskProgress';

const TABS = [
  { id: 'tasks', label: 'Tasks' },
  { id: 'progress', label: 'Progress' },
  { id: 'summary', label: 'Summary' },
];

export default function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [tips, setTips] = useState([]);
  const [progressCalendar, setProgressCalendar] = useState(null);
  const [currentScreen, setCurrentScreen] = useState('PORTAL');
  const [activeTab, setActiveTab] = useState('tasks');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchPortalData()
      .then((data) => {
        setMetadata(data.metadata);
        setTasks(data.tasks);
        setTips(data.tips);
        setProgressCalendar(data.progressCalendar || null);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleTaskUpdate = useCallback((taskId, updatedTask) => {
    setTasks((prev) => prev.map((t) => (t.id === taskId ? updatedTask : t)));
  }, []);

  const handleTasksSync = useCallback((result) => {
    if (result?.tasks?.length) setTasks(result.tasks);
    if (result?.progressCalendar) setProgressCalendar(result.progressCalendar);
  }, []);

  const handleSend = async () => {
    setSending(true);
    try {
      await sendToDoctor();
      setCurrentScreen('CONFIRMATION');
    } catch {
      setError('Could not send to doctor. Please try again.');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="portal-shell portal-shell--center">
        <p className="loading-text">Loading your care portal…</p>
      </div>
    );
  }

  if (error && !metadata) {
    return (
      <div className="portal-shell portal-shell--center">
        <p className="error-text">{error}</p>
      </div>
    );
  }

  if (currentScreen === 'CONFIRMATION') {
    return (
      <div className="portal-shell">
        <ConfirmationView metadata={metadata} tasks={tasks} onBack={() => setCurrentScreen('PORTAL')} />
      </div>
    );
  }

  const { patient, doctor, visit } = metadata;
  const completedCount = tasks.filter(isTaskCompleteForProgress).length;
  const allDone = tasks.length > 0 && completedCount === tasks.length;
  const visitSubtitle = visit.summaryPlain?.[0] || doctor.note;

  return (
    <div className="portal-shell">
      <header className="portal-header portal-header--compact">
        <div>
          <div className="portal-app-name">GP Copilot</div>
          <div className="portal-subtitle">Secure portal · Dr. {doctor.name.split(',')[0]}</div>
        </div>
      </header>

      <nav className="portal-tabs" aria-label="Portal sections">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`portal-tabs__btn ${activeTab === tab.id ? 'portal-tabs__btn--active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === 'tasks' ? (
        <>
          <ProgressHeader tasks={tasks} patientFirstName={patient.firstName} />

          {tasks.length ? (
            <TaskSection tasks={tasks} onUpdate={handleTaskUpdate} onTasksSync={handleTasksSync} />
          ) : (
            <section className="card task-section--empty">
              <p>Your doctor has not assigned tasks yet.</p>
            </section>
          )}

          <div className="portal-actions portal-actions--send">
            <button
              type="button"
              className="btn btn-primary btn-lg"
              onClick={handleSend}
              disabled={sending}
            >
              {sending ? 'Sending…' : allDone ? 'Send to my doctor' : 'Send progress to my doctor'}
            </button>
            {!allDone && tasks.length ? (
              <p className="portal-actions__hint">You can send now and finish remaining tasks later.</p>
            ) : null}
          </div>
        </>
      ) : null}

      {activeTab === 'progress' ? (
        <ProgressCalendar calendar={progressCalendar} tasks={tasks} />
      ) : null}

      {activeTab === 'summary' ? (
        <>
          <DownloadReport metadata={metadata} variant="featured" />
          <CollapsibleSection
            title="Visit summary"
            subtitle={visitSubtitle?.length > 60 ? `${visitSubtitle.slice(0, 60)}…` : visitSubtitle}
            defaultOpen
            variant="muted"
          >
            <VisitSummary visit={visit} compact />
            <div className="collapsible__divider" />
            <DoctorCard doctor={doctor} inline />
          </CollapsibleSection>
          <TipsSection tips={tips} />
        </>
      ) : null}

      {activeTab === 'tasks' ? (
        <DownloadReport metadata={metadata} variant="compact" />
      ) : null}

      <p className="privacy-notice">
        Secure message from {doctor.clinicName}. Questions? Call {doctor.contact.phone}.
      </p>
    </div>
  );
}
