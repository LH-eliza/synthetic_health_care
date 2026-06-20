import BPGauge from './BPGauge';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

export default function VisitSummary({ visit, compact = false }) {
  const bp = visit.metrics?.currentBP;

  if (compact) {
    return (
      <div className="visit-summary-compact">
        <div className="visit-summary__dates">
          <div>
            <span className="visit-summary__label">Last visit</span>
            <span className="visit-summary__date">{formatDate(visit.lastDate)}</span>
          </div>
          <div>
            <span className="visit-summary__label">Next visit</span>
            <span className="visit-summary__date">{formatDate(visit.nextDate)}</span>
          </div>
        </div>
        {bp?.systolic ? (
          <p className="visit-summary-compact__bp">
            Blood pressure at visit: <strong>{bp.systolic}/{bp.diastolic}</strong> mmHg
            <span className="visit-summary-compact__target">
              (target {visit.metrics.targetBP.systolic}/{visit.metrics.targetBP.diastolic})
            </span>
          </p>
        ) : null}
        {visit.summaryPlain?.length ? (
          <ul className="visit-summary__list visit-summary__list--compact">
            {visit.summaryPlain.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  return (
    <section className="card visit-summary">
      <div className="visit-summary__dates">
        <div>
          <span className="visit-summary__label">Last visit</span>
          <span className="visit-summary__date">{formatDate(visit.lastDate)}</span>
        </div>
        <div>
          <span className="visit-summary__label">Next visit</span>
          <span className="visit-summary__date">{formatDate(visit.nextDate)}</span>
        </div>
      </div>
      <BPGauge
        currentBP={visit.metrics.currentBP}
        targetBP={visit.metrics.targetBP}
        status={visit.metrics.status}
      />
      {visit.summaryPlain?.length ? (
        <ul className="visit-summary__list">
          {visit.summaryPlain.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
