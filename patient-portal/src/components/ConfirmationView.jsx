export default function ConfirmationView({ metadata, tasks, onBack }) {
  const completedCount = tasks.filter((t) => t.isCompleted).length;
  const allDone = completedCount === tasks.length;
  const incomplete = tasks.filter((t) => !t.isCompleted);

  return (
    <div className="confirmation-view">
      <header className="confirmation-view__header">
        <h1>Sent — thank you, {metadata.patient.firstName}.</h1>
        <p>Your care team has received your pre-visit update.</p>
      </header>

      {!allDone ? (
        <div className="warning-card">
          <h2>Items still open</h2>
          <ul>
            {incomplete.map((t) => (
              <li key={t.id}>{t.title}</li>
            ))}
          </ul>
          <p className="warning-card__footer">No rush — you can come back using the same link</p>
        </div>
      ) : (
        <div className="success-card">
          <p>You&apos;ve completed everything. Well done.</p>
        </div>
      )}

      <button type="button" className="btn btn-secondary" onClick={onBack}>
        Back to portal
      </button>
    </div>
  );
}
