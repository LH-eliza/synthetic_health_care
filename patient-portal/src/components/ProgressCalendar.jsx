import { frequencyLabel } from '../utils/taskProgress';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function formatMonthLabel(monthStr) {
  if (!monthStr) return '';
  const [year, month] = monthStr.split('-').map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  });
}

function formatDayLabel(dateStr) {
  return new Date(`${dateStr}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

export default function ProgressCalendar({ calendar, tasks }) {
  if (!calendar) {
    return (
      <section className="card progress-calendar progress-calendar--empty">
        <p>Your activity will appear here as you complete daily and weekly tasks.</p>
      </section>
    );
  }

  const { days = [], today, stats = {}, entriesByDate = {} } = calendar;
  const recurringTasks = tasks.filter((t) => t.isRecurring);
  const selectedDate = today;
  const selectedEntries = entriesByDate[selectedDate] || [];

  const firstWeekday = days.length
    ? (new Date(`${days[0].date}T12:00:00`).getDay() + 6) % 7
    : 0;
  const padding = Array.from({ length: firstWeekday }, (_, i) => ({ pad: i }));

  return (
    <section className="progress-calendar" aria-label="Your progress">
      <div className="progress-calendar__stats">
        <div className="progress-stat">
          <span className="progress-stat__value">{stats.currentStreak ?? 0}</span>
          <span className="progress-stat__label">Day streak</span>
        </div>
        <div className="progress-stat">
          <span className="progress-stat__value">{stats.thisWeekCount ?? 0}</span>
          <span className="progress-stat__label">This week</span>
        </div>
        <div className="progress-stat">
          <span className="progress-stat__value">{stats.totalLogs ?? 0}</span>
          <span className="progress-stat__label">Total logs</span>
        </div>
      </div>

      {recurringTasks.length ? (
        <div className="progress-calendar__habits card">
          <h3 className="progress-calendar__section-title">Your routines</h3>
          <ul className="progress-habit-list">
            {recurringTasks.map((task) => (
              <li key={task.id} className="progress-habit-list__item">
                <div>
                  <strong>{task.title}</strong>
                  <span className="progress-habit-list__freq">{frequencyLabel(task.frequency)}</span>
                </div>
                <div className="progress-habit-list__meta">
                  {task.streak > 0 ? (
                    <span className="progress-habit-list__streak">{task.streak}-day streak</span>
                  ) : null}
                  <span className={task.loggedInPeriod ? 'progress-habit-list__done' : 'progress-habit-list__pending'}>
                    {task.loggedInPeriod ? '✓ On track' : 'Due now'}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="progress-calendar__grid card">
        <h3 className="progress-calendar__section-title">{formatMonthLabel(calendar.month)}</h3>
        <div className="calendar-grid" role="grid" aria-label="Activity calendar">
          <div className="calendar-grid__weekdays">
            {WEEKDAYS.map((d) => (
              <span key={d} className="calendar-grid__weekday">{d}</span>
            ))}
          </div>
          <div className="calendar-grid__days">
            {padding.map((p) => (
              <span key={`pad-${p.pad}`} className="calendar-grid__day calendar-grid__day--empty" />
            ))}
            {days.map((day) => {
              const isToday = day.date === today;
              const hasActivity = day.count > 0;
              return (
                <div
                  key={day.date}
                  className={[
                    'calendar-grid__day',
                    hasActivity ? 'calendar-grid__day--active' : '',
                    isToday ? 'calendar-grid__day--today' : '',
                  ].filter(Boolean).join(' ')}
                  title={`${day.date}: ${day.count} log(s)`}
                >
                  <span className="calendar-grid__date">{parseInt(day.date.slice(-2), 10)}</span>
                  {hasActivity ? (
                    <span className="calendar-grid__dot" aria-hidden="true">
                      {day.count > 1 ? day.count : '•'}
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
        <p className="progress-calendar__legend">
          <span className="calendar-grid__dot calendar-grid__dot--sample" /> = activity logged
        </p>
      </div>

      <div className="progress-calendar__log card">
        <h3 className="progress-calendar__section-title">Today&apos;s activity</h3>
        {selectedEntries.length ? (
          <ul className="progress-log-list">
            {selectedEntries.map((entry, idx) => (
              <li key={`${entry.taskId}-${idx}`} className="progress-log-list__item">
                <div>
                  <strong>{entry.title}</strong>
                  {entry.value ? <span className="progress-log-list__value">{entry.value}</span> : null}
                </div>
                {entry.time ? <span className="progress-log-list__time">{entry.time}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="progress-calendar__empty-day">
            Nothing logged yet for {formatDayLabel(selectedDate)}. Complete a daily task to start your streak.
          </p>
        )}
      </div>
    </section>
  );
}
