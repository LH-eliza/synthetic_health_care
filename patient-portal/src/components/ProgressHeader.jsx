import { getTaskMeta } from '../utils/taskMeta';
import { isTaskCompleteForProgress } from '../utils/taskProgress';

export default function ProgressHeader({ tasks, patientFirstName }) {
  const completedCount = tasks.filter(isTaskCompleteForProgress).length;
  const total = tasks.length;
  const pct = total ? (completedCount / total) * 100 : 100;
  const allDone = total === 0 || completedCount === total;
  const nextTask = tasks.find((t) => !isTaskCompleteForProgress(t));
  const recurringCount = tasks.filter((t) => t.isRecurring).length;

  if (total === 0) {
    return (
      <div className="progress-hero progress-hero--empty">
        <h2 className="progress-hero__greeting">Hi {patientFirstName}</h2>
        <p className="progress-hero__lead">No tasks right now — review your visit summary below.</p>
      </div>
    );
  }

  return (
    <div className="progress-hero">
      <div className="progress-hero__top">
        <div>
          <p className="progress-hero__eyebrow">Your action list</p>
          <h2 className="progress-hero__greeting">
            {allDone
              ? `All caught up, ${patientFirstName}!`
              : `${patientFirstName}, ${total - completedCount} item${total - completedCount === 1 ? '' : 's'} due now`}
          </h2>
        </div>
        <span className={`pill-badge ${allDone ? 'pill-badge--teal' : 'pill-badge--amber'}`}>
          {allDone ? 'On track today' : `${completedCount}/${total}`}
        </span>
      </div>

      <div className="progress-bar progress-bar--lg" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="progress-bar__fill" style={{ width: `${pct}%` }} />
      </div>

      {recurringCount > 0 ? (
        <p className="progress-hero__recurring-note">
          {recurringCount} daily or weekly routine{recurringCount === 1 ? '' : 's'} — check the <strong>Progress</strong> tab to see your calendar.
        </p>
      ) : null}

      {!allDone && nextTask ? (
        <div className="progress-hero__next">
          <span className="progress-hero__next-label">Start here</span>
          <span className="progress-hero__next-task">{nextTask.title}</span>
          <span className="progress-hero__next-type">{getTaskMeta(nextTask.type).label}</span>
        </div>
      ) : (
        <p className="progress-hero__lead progress-hero__lead--done">
          Tap <strong>Send to my doctor</strong> when you&apos;re ready.
        </p>
      )}
    </div>
  );
}

export function CompletedBadge() {
  return (
    <span className="completed-badge" aria-live="polite">
      ✓ Completed
    </span>
  );
}
