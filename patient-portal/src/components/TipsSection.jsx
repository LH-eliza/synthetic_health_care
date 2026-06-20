import { useState } from 'react';

const COLOR_MAP = {
  green: 'tip-chip--green',
  teal: 'tip-chip--teal',
  blue: 'tip-chip--blue',
  amber: 'tip-chip--amber',
  purple: 'tip-chip--purple',
};

export default function TipsSection({ tips }) {
  const [open, setOpen] = useState(false);

  return (
    <section className="card tips-section">
      <button
        type="button"
        className="accordion-trigger"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span className="tips-section__title">Helpful tips (optional)</span>
        <span className={`accordion-chevron ${open ? 'accordion-chevron--open' : ''}`}>›</span>
      </button>
      {open ? (
        <div className="accordion-body tips-grid">
          {tips.map((tip) => (
            <article key={tip.id} className={`tip-chip ${COLOR_MAP[tip.color] || ''}`}>
              <span className="tip-chip__category">{tip.category}</span>
              <h4 className="tip-chip__title">{tip.title}</h4>
              <p className="tip-chip__detail">{tip.detail}</p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
