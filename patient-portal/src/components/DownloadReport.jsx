import { useState } from 'react';
import { buildVisitReportText, downloadTextFile } from '../utils/downloadReport';

export default function DownloadReport({ metadata, variant = 'featured' }) {
  const [downloaded, setDownloaded] = useState(false);

  if (!metadata?.afterVisitReport) return null;

  const handleDownload = () => {
    const text = buildVisitReportText(metadata);
    const name = `${metadata.patient.firstName}_${metadata.patient.lastName}_after_visit_report.txt`;
    downloadTextFile(name, text);
    setDownloaded(true);
  };

  const highlights = [
    'Visit notes in plain language',
    'Medication changes & precautions',
    'Your follow-up task list',
  ];

  if (variant === 'compact') {
    return (
      <div className="download-compact">
        <button type="button" className="download-compact__btn" onClick={handleDownload}>
          {downloaded ? '✓ Report downloaded' : '↓ Download after-visit report'}
        </button>
      </div>
    );
  }

  return (
    <section className="card download-report">
      <div className="download-report__header">
        <div className="download-report__icon" aria-hidden="true">📄</div>
        <div>
          <h3 className="download-report__title">After-Visit Report</h3>
          <p className="download-report__desc">
            Save a copy of today&apos;s visit summary, medication changes, and care instructions.
          </p>
        </div>
      </div>
      <ul className="download-report__highlights">
        {highlights.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <button type="button" className="btn btn-primary btn-lg download-report__btn" onClick={handleDownload}>
        {downloaded ? '✓ Report downloaded — tap to save again' : '↓ Download your visit summary'}
      </button>
      <p className="download-report__hint">Plain-text file you can print or keep for your records.</p>
    </section>
  );
}
