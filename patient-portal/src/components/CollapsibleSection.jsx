import { useState } from 'react';

export default function CollapsibleSection({
  title,
  subtitle,
  children,
  defaultOpen = false,
  variant = 'default',
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={`card collapsible ${variant === 'muted' ? 'collapsible--muted' : ''}`}>
      <button
        type="button"
        className="accordion-trigger collapsible__trigger"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <div>
          <div className="collapsible__title">{title}</div>
          {subtitle && !open ? (
            <div className="collapsible__subtitle">{subtitle}</div>
          ) : null}
        </div>
        <span className={`accordion-chevron ${open ? 'accordion-chevron--open' : ''}`}>›</span>
      </button>
      {open ? <div className="accordion-body collapsible__body">{children}</div> : null}
    </section>
  );
}
