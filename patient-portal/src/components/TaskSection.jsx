import { useState, useRef } from 'react';
import { submitTask } from '../api';
import { getTaskMeta } from '../utils/taskMeta';
import { frequencyLabel, periodDoneLabel } from '../utils/taskProgress';

function CheckboxTask({ task, onUpdate, onSync }) {
  const toggle = async () => {
    if (task.isRecurring && task.loggedInPeriod) return;
    const next = !task.isCompleted;
    onUpdate(task.id, { ...task, isCompleted: next, loggedInPeriod: next });
    if (task.dbTaskId && next) {
      const result = await submitTask(task.id, {
        type: task.type,
        dbTaskId: task.dbTaskId,
        payload: {},
      });
      onSync?.(result);
    }
  };

  const label = task.isRecurring && task.loggedInPeriod
    ? periodDoneLabel(task)
    : (task.isCompleted ? 'Completed' : getTaskMeta(task.type).cta);

  return (
    <button
      type="button"
      className="task-action-btn"
      onClick={toggle}
      disabled={task.isRecurring && task.loggedInPeriod}
    >
      <span className={`task-action-btn__box ${task.isCompleted || task.loggedInPeriod ? 'task-action-btn__box--checked' : ''}`}>
        {task.isCompleted || task.loggedInPeriod ? '✓' : ''}
      </span>
      <span>{label}</span>
    </button>
  );
}

function FileUploadTask({ task, onUpdate, onSync }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = async (file) => {
    if (!file) return;
    onUpdate(task.id, { ...task, isCompleted: true, payload: file.name });
    if (task.dbTaskId) {
      const result = await submitTask(task.id, {
        type: task.type,
        dbTaskId: task.dbTaskId,
        payload: { filename: file.name },
      });
      onSync?.(result);
    }
  };

  return (
    <div className="task-control">
      <input ref={inputRef} type="file" hidden onChange={(e) => handleFile(e.target.files[0])} />
      <div
        className={`task-upload__drop ${dragOver ? 'task-upload__drop--active' : ''} ${task.payload ? 'task-upload__drop--done' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        {task.payload ? (
          <>
            <span className="task-upload__icon">✓</span>
            <span className="task-upload__filename">{task.payload}</span>
            <span className="task-upload__hint">Tap to replace</span>
          </>
        ) : (
          <>
            <span className="task-upload__icon">↑</span>
            <span className="task-upload__prompt">{getTaskMeta(task.type).cta}</span>
            <span className="task-upload__hint">PDF or photo</span>
          </>
        )}
      </div>
    </div>
  );
}

function BPLogTask({ task, onUpdate, onSync }) {
  const [sys, setSys] = useState('');
  const [dia, setDia] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    const systolic = parseInt(sys, 10);
    const diastolic = parseInt(dia, 10);
    if (!systolic || !diastolic) return;

    const reading = { systolic, diastolic };
    if (task.dbTaskId) {
      const result = await submitTask(task.id, {
        type: task.type,
        dbTaskId: task.dbTaskId,
        payload: { reading },
      });
      onSync?.(result);
    } else {
      onUpdate(task.id, {
        ...task,
        isCompleted: true,
        loggedInPeriod: true,
        payload: [...(task.payload || []), reading],
      });
    }
    setSys('');
    setDia('');
  };

  const lastReading = task.payload?.length
    ? task.payload[task.payload.length - 1]
    : null;

  return (
    <div className="task-control">
      {lastReading ? (
        <div className="task-bp__recent">
          Last: <strong>{lastReading.systolic}/{lastReading.diastolic}</strong> mmHg
        </div>
      ) : null}
      {task.isRecurring && task.loggedInPeriod ? (
        <div className="task-period-banner task-period-banner--done">
          ✓ {periodDoneLabel(task)} — you can log again tomorrow
        </div>
      ) : null}
      <form className="task-bp__form" onSubmit={submit}>
        <div className="task-bp__inputs">
          <label className="task-bp__field">
            <span>Systolic</span>
            <input type="number" placeholder="120" value={sys} onChange={(e) => setSys(e.target.value)} min="70" max="250" required />
          </label>
          <span className="task-bp__slash">/</span>
          <label className="task-bp__field">
            <span>Diastolic</span>
            <input type="number" placeholder="80" value={dia} onChange={(e) => setDia(e.target.value)} min="40" max="150" required />
          </label>
        </div>
        <button type="submit" className="btn btn-secondary btn-block">
          {task.isRecurring && task.loggedInPeriod ? 'Log another reading' : getTaskMeta(task.type).cta}
        </button>
      </form>
    </div>
  );
}

function NotesTask({ task, onUpdate, onSync }) {
  const [text, setText] = useState(task.payload?.text || '');
  const inputRef = useRef(null);

  const save = async () => {
    const attachment = task.payload?.attachment || null;
    onUpdate(task.id, { ...task, isCompleted: true, payload: { text, attachment } });
    if (task.dbTaskId) {
      const result = await submitTask(task.id, {
        type: task.type,
        dbTaskId: task.dbTaskId,
        payload: { text, attachment },
      });
      onSync?.(result);
    }
  };

  return (
    <div className="task-control">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Brief notes for your doctor…"
        rows={3}
        className="task-notes__input"
      />
      <div className="task-notes__actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => inputRef.current?.click()}>Attach file</button>
        <input ref={inputRef} type="file" hidden onChange={(e) => {
          const file = e.target.files[0];
          if (file) onUpdate(task.id, { ...task, payload: { text, attachment: file.name } });
        }} />
        <button type="button" className="btn btn-primary btn-sm" onClick={save}>{getTaskMeta(task.type).cta}</button>
      </div>
    </div>
  );
}

function TaskControl({ task, onUpdate, onSync }) {
  switch (task.type) {
    case 'file_upload': return <FileUploadTask task={task} onUpdate={onUpdate} onSync={onSync} />;
    case 'bp_log': return <BPLogTask task={task} onUpdate={onUpdate} onSync={onSync} />;
    case 'notes_textarea': return <NotesTask task={task} onUpdate={onUpdate} onSync={onSync} />;
    default: return <CheckboxTask task={task} onUpdate={onUpdate} onSync={onSync} />;
  }
}

function TaskCard({ task, step, isActive, onUpdate, onSync, showStep = true }) {
  const meta = getTaskMeta(task.type);
  const doneForPeriod = task.isRecurring ? task.loggedInPeriod : task.isCompleted;
  const showBody = !task.isRecurring
    ? !task.isCompleted
    : task.type === 'bp_log' || !task.loggedInPeriod;

  return (
    <article
      className={`task-card ${doneForPeriod ? 'task-card--done' : ''} ${isActive ? 'task-card--active' : ''} ${task.isRecurring ? 'task-card--recurring' : ''}`}
      aria-current={isActive ? 'step' : undefined}
    >
      <div className="task-card__header">
        {showStep ? (
          <div className={`task-card__step ${doneForPeriod ? 'task-card__step--done' : ''}`}>
            {doneForPeriod ? '✓' : step}
          </div>
        ) : null}
        <div className="task-card__headings">
          <div className="task-card__labels">
            <span className="task-card__type">{meta.label}</span>
            {task.isRecurring ? (
              <span className="task-card__frequency">{frequencyLabel(task.frequency)}</span>
            ) : null}
            {task.isRecurring && task.streak > 0 ? (
              <span className="task-card__streak">{task.streak}-day streak</span>
            ) : null}
          </div>
          <h3 className="task-card__title">{task.title}</h3>
          {!doneForPeriod ? <p className="task-card__action">{meta.action}</p> : null}
        </div>
      </div>

      {showBody ? (
        <div className="task-card__body">
          <TaskControl task={task} onUpdate={onUpdate} onSync={onSync} />
        </div>
      ) : (
        <div className="task-period-banner task-period-banner--done">
          ✓ {periodDoneLabel(task)}
        </div>
      )}
    </article>
  );
}

export default function TaskSection({ tasks, onUpdate, onTasksSync }) {
  const [showCompleted, setShowCompleted] = useState(false);
  const syncTasks = (result) => {
    if (result?.tasks?.length) onTasksSync?.(result);
  };

  const habits = tasks.filter((t) => t.isRecurring);
  const oncePending = tasks.filter((t) => !t.isRecurring && !t.isCompleted);
  const onceCompleted = tasks.filter((t) => !t.isRecurring && t.isCompleted);
  const firstPendingId = oncePending[0]?.id || habits.find((t) => !t.loggedInPeriod)?.id;

  if (!tasks.length) return null;

  let step = 0;

  return (
    <section className="task-flow" aria-label="Your tasks">
      {habits.length ? (
        <div className="task-habits">
          <h3 className="task-habits__title">Daily &amp; weekly routines</h3>
          <p className="task-habits__lead">These reset each day or week — keep logging to build your streak.</p>
          {habits.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              step={0}
              isActive={task.id === firstPendingId}
              onUpdate={onUpdate}
              onSync={syncTasks}
              showStep={false}
            />
          ))}
        </div>
      ) : null}

      {oncePending.map((task) => {
        step += 1;
        return (
          <TaskCard
            key={task.id}
            task={task}
            step={step}
            isActive={task.id === firstPendingId}
            onUpdate={onUpdate}
            onSync={syncTasks}
          />
        );
      })}

      {onceCompleted.length ? (
        <div className="task-completed-group">
          <button
            type="button"
            className="task-completed-group__toggle"
            aria-expanded={showCompleted}
            onClick={() => setShowCompleted(!showCompleted)}
          >
            <span>Completed ({onceCompleted.length})</span>
            <span className={`accordion-chevron ${showCompleted ? 'accordion-chevron--open' : ''}`}>›</span>
          </button>
          {showCompleted ? (
            <div className="task-completed-group__list">
              {onceCompleted.map((task) => (
                <div key={task.id} className="task-completed-item">
                  <span className="task-completed-item__check">✓</span>
                  <span>{task.title}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
