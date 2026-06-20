function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function section(title, lines) {
  if (!lines || (Array.isArray(lines) && lines.length === 0)) return [];
  return ['', title, '-'.repeat(title.length), ...(Array.isArray(lines) ? lines : [lines])];
}

function bulletList(items) {
  return items.map((item) => `  • ${item}`);
}

function statusLabel(status) {
  const map = {
    good: 'On target',
    warning: 'Above target — monitor closely',
    critical: 'Well above target — follow precautions',
    neutral: 'Not recorded at visit',
  };
  return map[status] || status;
}

export function buildVisitReportText(metadata) {
  const { patient, doctor, visit, afterVisitReport: report } = metadata;
  const lines = [
    report?.title?.toUpperCase() || 'AFTER-VISIT REPORT',
    '='.repeat(40),
    '',
    `Patient: ${patient.firstName} ${patient.lastName}`,
    `Patient ID: ${patient.id}`,
    '',
    'YOUR CARE TEAM',
    '---------------',
    `${doctor.name} — ${doctor.specialty}`,
    doctor.clinicName,
    doctor.contact.address,
    `${doctor.city}`,
    `Phone: ${doctor.contact.phone}`,
    `Email: ${doctor.contact.email}`,
    '',
    'VISIT DATES',
    '-----------',
    `Visit date:    ${formatDate(visit.lastDate)}`,
    `Next visit:    ${formatDate(visit.nextDate)}`,
  ];

  if (report?.visitReason) {
    lines.push(`Reason:        ${report.visitReason}`);
  }

  const bp = visit.metrics?.currentBP;
  lines.push('', 'VITALS AT VISIT', '---------------');
  if (bp?.systolic) {
    lines.push(`Blood pressure: ${bp.systolic}/${bp.diastolic} mmHg`);
    lines.push(
      `Target:         ${visit.metrics.targetBP.systolic}/${visit.metrics.targetBP.diastolic} mmHg`,
    );
    lines.push(`Status:         ${statusLabel(visit.metrics.status)}`);
  } else {
    lines.push('Blood pressure: Not recorded at this visit');
  }

  if (report?.keyFindings?.length) {
    lines.push(...section('WHAT WE DISCUSSED', bulletList(report.keyFindings)));
  } else if (visit.summaryPlain?.length) {
    lines.push(...section('VISIT SUMMARY', bulletList(visit.summaryPlain)));
  }

  if (report?.medicationChanges?.length) {
    lines.push(...section('MEDICATION CHANGES', bulletList(report.medicationChanges)));
  }

  if (report?.doctorRemarks) {
    lines.push(...section('NOTE FROM YOUR DOCTOR', report.doctorRemarks));
  } else if (doctor.note) {
    lines.push(...section('NOTE FROM YOUR DOCTOR', doctor.note));
  }

  if (report?.precautions?.length) {
    lines.push(...section('PRECAUTIONS & IMPORTANT INFORMATION', bulletList(report.precautions)));
  }

  if (report?.followUpTasks?.length) {
    lines.push(...section('YOUR PRE-VISIT TASKS', bulletList(report.followUpTasks)));
    lines.push('  Complete these before your next appointment.');
  }

  if (report?.lifestyleGuidance?.length) {
    lines.push('', 'LIFESTYLE GUIDANCE', '------------------');
    report.lifestyleGuidance.forEach((tip) => {
      lines.push(`  • ${tip.title}: ${tip.detail}`);
    });
  }

  if (report?.emergencyNotice) {
    lines.push('', 'WHEN TO SEEK URGENT CARE', '------------------------', report.emergencyNotice);
  }

  lines.push(
    '',
    '—',
    'This report summarizes your visit for personal reference.',
    'It does not replace medical advice. Contact your clinic with questions.',
    '',
    `Generated: ${new Date().toLocaleString()}`,
  );

  return lines.join('\n');
}

export function downloadTextFile(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
