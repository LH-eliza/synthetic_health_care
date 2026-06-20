import { systolicToAngle } from '../utils/bpGauge';

const ARC = {
  teal: '#0D9488',
  amber: '#F59E0B',
  grey: '#6B7280',
};

export default function BPGauge({ currentBP, targetBP, status }) {
  const sys = currentBP?.systolic || 0;
  const angle = systolicToAngle(sys);
  const cx = 120;
  const cy = 110;
  const r = 80;

  const polar = (deg, radius = r) => {
    const rad = ((180 - deg) * Math.PI) / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy - radius * Math.sin(rad),
    };
  };

  const arcPath = (startDeg, endDeg) => {
    const start = polar(startDeg);
    const end = polar(endDeg);
    const large = endDeg - startDeg > 90 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}`;
  };

  const needleEnd = polar(angle, r - 12);
  const statusLabel =
    status === 'good'
      ? 'On target'
      : status === 'warning'
        ? 'Getting there'
        : status === 'critical'
          ? 'Above target'
          : 'No reading';

  return (
    <div className="bp-gauge">
      <svg viewBox="0 0 240 140" className="bp-gauge__svg" aria-hidden="true">
        <path d={arcPath(0, 60)} fill="none" stroke={ARC.teal} strokeWidth="14" strokeLinecap="round" />
        <path d={arcPath(60, 120)} fill="none" stroke={ARC.amber} strokeWidth="14" strokeLinecap="round" />
        <path d={arcPath(120, 180)} fill="none" stroke={ARC.grey} strokeWidth="14" strokeLinecap="round" />
        <line
          x1={cx}
          y1={cy}
          x2={needleEnd.x}
          y2={needleEnd.y}
          stroke="#1F2937"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="6" fill="#1F2937" />
      </svg>
      <div className="bp-gauge__reading">
        {sys ? (
          <>
            <span className="bp-gauge__value">{sys}/{currentBP.diastolic}</span>
            <span className="bp-gauge__unit">mmHg</span>
          </>
        ) : (
          <span className="bp-gauge__value bp-gauge__value--empty">—</span>
        )}
      </div>
      <div className="bp-gauge__meta">
        <span className={`bp-gauge__status bp-gauge__status--${status}`}>{statusLabel}</span>
        {targetBP?.systolic ? (
          <span className="bp-gauge__target">Target: {targetBP.systolic}/{targetBP.diastolic}</span>
        ) : null}
      </div>
    </div>
  );
}
