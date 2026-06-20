/* =========================================================================
   app.js — GP Copilot client-side logic
   ========================================================================= */

// -------------------------------------------------------------------------
// Sidebar collapse/expand
// -------------------------------------------------------------------------
document.querySelectorAll('.sidebar-panel-header').forEach(header => {
  header.addEventListener('click', () => {
    const panel = header.closest('.sidebar-panel');
    panel.classList.toggle('open');
    header.classList.toggle('active');
  });
});

// Open first panel in each sidebar by default
document.querySelectorAll('.sidebar-left .sidebar-panel:first-child, .sidebar-right .sidebar-panel:first-child')
  .forEach(p => { p.classList.add('open'); p.querySelector('.sidebar-panel-header')?.classList.add('active'); });

// -------------------------------------------------------------------------
// Utility: show/hide spinner on button
// -------------------------------------------------------------------------
function setButtonLoading(btn, loading, label = null) {
  if (loading) {
    btn._origHTML = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span>${label || 'Working…'}`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._origHTML || btn.innerHTML;
    btn.disabled = false;
  }
}

// -------------------------------------------------------------------------
// Utility: show alert above a container
// -------------------------------------------------------------------------
function showAlert(container, type, message, autoDismiss = 4000) {
  const icons = {
    info:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" width="15" height="15"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>',
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" width="15" height="15"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4 12 14.01l-3-3"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" width="15" height="15"><path d="m10.29 3.86-8.17 14.16a2 2 0 0 0 1.71 3h16.34a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
    danger:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" width="15" height="15"><circle cx="12" cy="12" r="9"/><path d="m15 9-6 6M9 9l6 6"/></svg>',
  };
  const el = document.createElement('div');
  el.className = `alert alert-${type}`;
  el.innerHTML = `${icons[type] || ''}<span>${message}</span>`;
  container.prepend(el);
  if (autoDismiss) setTimeout(() => el.remove(), autoDismiss);
}

// -------------------------------------------------------------------------
// Flow A — Transcribe + confirm bins
// -------------------------------------------------------------------------
const transcribeBtn = document.getElementById('btn-transcribe');
const scribeTextarea = document.getElementById('scribe-conversation');
const binsContainer = document.getElementById('bins-container');
const confirmAllBtn = document.getElementById('btn-confirm-all');

// Track per-bin confirm state
const binState = {
  social_history: { confirmed: false, data: null },
  medical_history: { confirmed: false, data: null },
  medications: { confirmed: false, data: null },
  vaccines: { confirmed: false, data: null },
};

function checkAllConfirmed() {
  const populated = Object.values(binState).filter(s => s.data !== null);
  const confirmed = populated.filter(s => s.confirmed);
  if (confirmAllBtn) {
    confirmAllBtn.disabled = populated.length === 0 || confirmed.length < populated.length;
  }
}

function renderBinContent(key, data) {
  const el = document.getElementById(`bin-content-${key}`);
  if (!el) return;
  el.classList.add('populated');
  if (Array.isArray(data)) {
    if (data.length === 0) {
      el.textContent = '(none mentioned)';
      return;
    }
    el.innerHTML = data.map(item => {
      if (typeof item === 'object') {
        return `<div class="sidebar-med">
          <span class="sidebar-med-name">${item.name || ''}</span>
          <span class="sidebar-med-detail">${item.dose || ''} ${item.frequency || ''}</span>
        </div>`;
      }
      return `<span class="sidebar-tag">${item}</span>`;
    }).join('');
  } else if (typeof data === 'object' && data !== null) {
    const entries = Object.entries(data).filter(([, v]) => v && v !== null);
    if (entries.length === 0) {
      el.textContent = '(none mentioned)';
      return;
    }
    el.innerHTML = entries.map(([k, v]) => {
      const label = k.replace(/_/g, ' ');
      if (Array.isArray(v)) {
        return v.length ? `<div class="sidebar-item"><strong>${label}:</strong> ${v.join(', ')}</div>` : '';
      }
      return v ? `<div class="sidebar-item"><strong>${label}:</strong> ${v}</div>` : '';
    }).join('');
  } else {
    el.textContent = data || '(none mentioned)';
  }
}

function enableBinConfirm(key) {
  const btn = document.getElementById(`btn-confirm-${key}`);
  if (btn) {
    btn.disabled = false;
    btn.classList.remove('btn-secondary');
    btn.classList.add('btn-primary');
  }
}

if (transcribeBtn) {
  transcribeBtn.addEventListener('click', async () => {
    const text = scribeTextarea?.value?.trim();
    if (!text) {
      showAlert(document.getElementById('flow-a-alerts'), 'warning', 'Please enter conversation text first.');
      return;
    }

    setButtonLoading(transcribeBtn, true, 'Structuring…');

    try {
      const patientId = document.body.dataset.patientId;
      const resp = await fetch(`/flow-a/${patientId}/transcribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_text: text }),
      });
      const data = await resp.json();

      if (!resp.ok || data.error) {
        showAlert(document.getElementById('flow-a-alerts'), 'danger', data.error || 'Transcription failed.');
        return;
      }

      const bins = data.bins;
      // Render each bin
      for (const [key, value] of Object.entries(bins)) {
        binState[key] = { confirmed: false, data: value };
        renderBinContent(key, value);
        enableBinConfirm(key);
      }
      showAlert(document.getElementById('flow-a-alerts'), 'success', 'Conversation structured into bins. Review and confirm each section.');
    } catch (err) {
      showAlert(document.getElementById('flow-a-alerts'), 'danger', `Network error: ${err.message}`);
    } finally {
      setButtonLoading(transcribeBtn, false);
    }
  });
}

// Per-bin confirm buttons
['social_history', 'medical_history', 'medications', 'vaccines'].forEach(key => {
  const btn = document.getElementById(`btn-confirm-${key}`);
  if (!btn) return;
  btn.addEventListener('click', () => {
    binState[key].confirmed = true;
    btn.innerHTML = '<span class="confirmed-badge"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M20 6 9 17l-5-5"/></svg> Confirmed</span>';
    btn.className = 'btn btn-sm';
    btn.style.cursor = 'default';
    btn.disabled = true;
    const binCard = document.getElementById(`bin-card-${key}`);
    if (binCard) binCard.classList.add('confirmed');
    checkAllConfirmed();
  });
});

// Confirm all → save to DB
if (confirmAllBtn) {
  confirmAllBtn.addEventListener('click', async () => {
    const bins = {};
    for (const [key, state] of Object.entries(binState)) {
      if (state.data !== null) bins[key] = state.data;
    }

    setButtonLoading(confirmAllBtn, true, 'Saving baseline…');
    try {
      const patientId = document.body.dataset.patientId;
      const resp = await fetch(`/flow-a/${patientId}/confirm-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bins }),
      });
      const data = await resp.json();
      if (!resp.ok || data.error) {
        showAlert(document.getElementById('flow-a-alerts'), 'danger', data.error);
        return;
      }
      showAlert(document.getElementById('flow-a-alerts'), 'success',
        'Baseline record established. This becomes the prior-visit data for future encounters.');
      confirmAllBtn.disabled = true;
      document.getElementById('baseline-established-banner')?.classList.remove('hidden');
    } catch (err) {
      showAlert(document.getElementById('flow-a-alerts'), 'danger', `Save failed: ${err.message}`);
    } finally {
      setButtonLoading(confirmAllBtn, false);
    }
  });
}

// -------------------------------------------------------------------------
// Flow B — Start visit
// -------------------------------------------------------------------------
const startVisitBtn = document.getElementById('btn-start-visit');
const visitReasonInput = document.getElementById('visit-reason-input');
let activeVisitId = null;

if (startVisitBtn) {
  startVisitBtn.addEventListener('click', async () => {
    const reason = visitReasonInput?.value?.trim() || 'Unspecified';
    setButtonLoading(startVisitBtn, true, 'Starting visit…');
    try {
      const patientId = document.body.dataset.patientId;
      const resp = await fetch(`/flow-b/${patientId}/start-visit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visit_reason: reason }),
      });
      const data = await resp.json();
      if (!resp.ok || data.error) {
        showAlert(document.getElementById('flow-b-alerts'), 'danger', data.error);
        return;
      }
      activeVisitId = data.visit_id;
      document.getElementById('active-visit-id')?.setAttribute('value', activeVisitId);
      document.getElementById('visit-started-section')?.classList.remove('hidden');
      document.getElementById('start-visit-section')?.classList.add('hidden');
      showAlert(document.getElementById('flow-b-alerts'), 'info',
        `Visit started (reason: ${reason}). Pre-visit chips remain active for reference.`);
    } catch (err) {
      showAlert(document.getElementById('flow-b-alerts'), 'danger', `Error: ${err.message}`);
    } finally {
      setButtonLoading(startVisitBtn, false);
    }
  });
}

// -------------------------------------------------------------------------
// Flow B — Generate dual note
// -------------------------------------------------------------------------
const generateNoteBtn = document.getElementById('btn-generate-note');
const visitNotesTextarea = document.getElementById('visit-notes-textarea');
const dualOutputSection = document.getElementById('dual-output-section');
const chartEntryOutput = document.getElementById('chart-entry-output');
const patientSummaryOutput = document.getElementById('patient-summary-output');
let generatedOutput = null;

if (generateNoteBtn) {
  generateNoteBtn.addEventListener('click', async () => {
    const notes = visitNotesTextarea?.value?.trim();
    if (!notes) {
      showAlert(document.getElementById('flow-b-alerts'), 'warning', 'Enter visit notes before generating.');
      return;
    }
    setButtonLoading(generateNoteBtn, true, 'Generating…');
    try {
      const patientId = document.body.dataset.patientId;
      const resp = await fetch(`/flow-b/${patientId}/generate-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visit_notes: notes }),
      });
      const data = await resp.json();
      if (!resp.ok || data.error) {
        showAlert(document.getElementById('flow-b-alerts'), 'danger', data.error);
        return;
      }
      generatedOutput = data.output;
      if (chartEntryOutput) chartEntryOutput.textContent = generatedOutput.chart_entry;
      if (patientSummaryOutput) patientSummaryOutput.textContent = generatedOutput.patient_summary;
      dualOutputSection?.classList.remove('hidden');
      document.getElementById('confirm-note-section')?.classList.remove('hidden');
      showAlert(document.getElementById('flow-b-alerts'), 'success',
        'Dual output generated — one prompt, two targets. Review before confirming.');
    } catch (err) {
      showAlert(document.getElementById('flow-b-alerts'), 'danger', `Error: ${err.message}`);
    } finally {
      setButtonLoading(generateNoteBtn, false);
    }
  });
}

// -------------------------------------------------------------------------
// Flow B — Task builder
// -------------------------------------------------------------------------
const addTaskBtn = document.getElementById('btn-add-task');
const taskList = document.getElementById('task-list');
let taskCount = 0;

if (addTaskBtn) {
  addTaskBtn.addEventListener('click', () => {
    taskCount++;
    const today = new Date();
    const defaultDue = new Date(today.setDate(today.getDate() + 30)).toISOString().split('T')[0];
    const row = document.createElement('div');
    row.className = 'task-row';
    row.id = `task-row-${taskCount}`;
    row.innerHTML = `
      <input type="text" name="task_desc" placeholder="Task description…" required />
      <select name="task_type">
        <option value="confirmation">Confirmation</option>
        <option value="recurring_input">Reading</option>
      </select>
      <input type="date" name="task_due" value="${defaultDue}" />
      <button type="button" class="btn btn-sm btn-danger" onclick="this.closest('.task-row').remove()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    `;
    taskList?.appendChild(row);
  });
}

// -------------------------------------------------------------------------
// Flow B — Confirm note + tasks
// -------------------------------------------------------------------------
const confirmNoteBtn = document.getElementById('btn-confirm-note');

if (confirmNoteBtn) {
  confirmNoteBtn.addEventListener('click', async () => {
    if (!generatedOutput) {
      showAlert(document.getElementById('flow-b-alerts'), 'warning', 'Generate note first.');
      return;
    }
    const patientId = document.body.dataset.patientId;
    const visitId = activeVisitId || document.getElementById('active-visit-id')?.value;

    // Collect tasks from task builder
    const tasks = [];
    document.querySelectorAll('.task-row').forEach(row => {
      const desc = row.querySelector('[name="task_desc"]')?.value?.trim();
      const type = row.querySelector('[name="task_type"]')?.value;
      const due = row.querySelector('[name="task_due"]')?.value;
      if (desc && due) {
        tasks.push({ description: desc, type, due_date: due });
      }
    });

    setButtonLoading(confirmNoteBtn, true, 'Saving visit…');
    try {
      const resp = await fetch(`/flow-b/${patientId}/confirm-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: visitId,
          chart_entry: generatedOutput.chart_entry,
          patient_summary: generatedOutput.patient_summary,
          tasks,
        }),
      });
      const data = await resp.json();
      if (!resp.ok || data.error) {
        showAlert(document.getElementById('flow-b-alerts'), 'danger', data.error);
        return;
      }
      showAlert(document.getElementById('flow-b-alerts'), 'success',
        `✅ Visit saved. ${data.task_count} follow-up tasks created. ${data.message}`);
      document.getElementById('send-portal-section')?.classList.remove('hidden');
      document.getElementById('saved-visit-id')?.setAttribute('value', visitId);
      confirmNoteBtn.disabled = true;
    } catch (err) {
      showAlert(document.getElementById('flow-b-alerts'), 'danger', `Error: ${err.message}`);
    } finally {
      setButtonLoading(confirmNoteBtn, false);
    }
  });
}

// -------------------------------------------------------------------------
// Flow B — Send portal
// -------------------------------------------------------------------------
const sendPortalBtn = document.getElementById('btn-send-portal');
const portalLinkDisplay = document.getElementById('portal-link-display');

if (sendPortalBtn) {
  sendPortalBtn.addEventListener('click', async () => {
    const patientId = document.body.dataset.patientId;
    const visitId = activeVisitId || document.getElementById('saved-visit-id')?.value
                    || document.getElementById('active-visit-id')?.value;

    setButtonLoading(sendPortalBtn, true, 'Generating secure link…');
    try {
      const resp = await fetch(`/flow-b/${patientId}/send-portal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visit_id: visitId }),
      });
      const data = await resp.json();
      if (!resp.ok || data.error) {
        showAlert(document.getElementById('flow-b-alerts'), 'danger', data.error);
        return;
      }
      if (portalLinkDisplay) {
        portalLinkDisplay.textContent = data.portal_url;
        portalLinkDisplay.href = data.portal_url;
        portalLinkDisplay.closest('.ocean-link-result')?.classList.remove('hidden');
      }
      document.getElementById('ocean-sent-status')?.classList.remove('hidden');
      showAlert(document.getElementById('flow-b-alerts'), 'success',
        'Secure link sent. Patient will receive their care summary via secure message.');
      sendPortalBtn.disabled = true;
    } catch (err) {
      showAlert(document.getElementById('flow-b-alerts'), 'danger', `Error: ${err.message}`);
    } finally {
      setButtonLoading(sendPortalBtn, false);
    }
  });
}
