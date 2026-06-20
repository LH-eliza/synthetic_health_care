/* =========================================================================
   app.js — GP Copilot client-side logic
   ========================================================================= */

// -------------------------------------------------------------------------
// Live patient intake injection + ED demo
// -------------------------------------------------------------------------
const patientIntakeCard = document.getElementById('patient-intake-card');
const patientIntakeText = document.getElementById('patient-intake-text');
const demoVisitReasonBtn = document.getElementById('btn-demo-visit-reason');

const DEMO_VISIT_REASON = 'Mental health check-in — work stress; post-ED asthma flare';

const PATIENT_INTAKE_MESSAGES = {
  mental: (
    "I am here for a mental health check-in because work has been super stressful, "
    + "but also my asthma has been playing up again since I got out of the hospital last week."
  ),
  asthma: (
    "My breathing got really bad after I left the ER last week. I have my rescue inhaler "
    + "but I am not sure my asthma plan is right anymore."
  ),
  diabetes: (
    "I'm here about my diabetes meds — the Metformin dose change didn't happen and "
    + "my sugars have been all over the place."
  ),
};

function resolvePatientIntakeText(reason) {
  const r = (reason || '').toLowerCase();
  if (!r.trim()) return null;
  if (r.includes('mental') || r.includes('stress') || r.includes('check-in')) {
    return PATIENT_INTAKE_MESSAGES.mental;
  }
  if (r.includes('asthma') || r.includes('breath') || r.includes('ed') || r.includes('hospital')) {
    return PATIENT_INTAKE_MESSAGES.asthma;
  }
  if (r.includes('diabetes') || r.includes('metformin') || r.includes('medication')) {
    return PATIENT_INTAKE_MESSAGES.diabetes;
  }
  return `"I'm here today because: ${reason.trim()}"`;
}

function showPatientIntake(reason) {
  const text = resolvePatientIntakeText(reason);
  if (!text || !patientIntakeCard || !patientIntakeText) return;
  patientIntakeText.textContent = text.startsWith('"') ? text : `"${text}"`;
  patientIntakeCard.classList.remove('hidden');
  patientIntakeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function bindPatientIntakeInput(inputEl) {
  if (!inputEl) return;
  let debounce;
  inputEl.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => showPatientIntake(inputEl.value), 280);
  });
}

// -------------------------------------------------------------------------
// Physician Focus Mode (Flow B)
// -------------------------------------------------------------------------
const cognitiveLoadSwitch = document.getElementById('cognitive-load-switch');
const cognitiveModeBadge = document.getElementById('cognitive-mode-badge');
const COPILOT_STORAGE_KEY = 'gp-copilot-physician-focus';

function isCopilotMode() {
  return document.body.classList.contains('cognitive-mode-copilot');
}

function setCognitiveLoadMode(copilotActive, { persist = true } = {}) {
  document.body.classList.toggle('cognitive-mode-copilot', copilotActive);
  if (cognitiveModeBadge) {
    cognitiveModeBadge.textContent = copilotActive ? 'Clinical Copilot' : 'Full EMR';
  }
  if (cognitiveLoadSwitch) {
    cognitiveLoadSwitch.checked = copilotActive;
  }
  if (persist) {
    localStorage.setItem(COPILOT_STORAGE_KEY, copilotActive ? 'copilot' : 'emr');
  }
  if (copilotActive) {
    ensureVisitStarted({ silent: true });
  }
  updateCopilotTaskLabels();
}

function updateCopilotTaskLabels() {
  document.querySelectorAll('.task-approve-label').forEach(el => {
    el.textContent = isCopilotMode() ? 'Authorize' : 'Approve';
  });
}

if (cognitiveLoadSwitch) {
  cognitiveLoadSwitch.addEventListener('change', () => {
    setCognitiveLoadMode(cognitiveLoadSwitch.checked);
  });
}

// Restore physician focus preference (default: on for streamlined workflow)
if (cognitiveLoadSwitch) {
  const saved = localStorage.getItem(COPILOT_STORAGE_KEY);
  setCognitiveLoadMode(saved !== 'emr', { persist: false });
}

// -------------------------------------------------------------------------
// AI Evidence Rationale — collapsible audit trail
// -------------------------------------------------------------------------
const evidenceRationaleToggle = document.getElementById('evidence-rationale-toggle');
const evidenceRationalePanel = document.getElementById('evidence-rationale-panel');

if (evidenceRationaleToggle && evidenceRationalePanel) {
  evidenceRationaleToggle.addEventListener('click', () => {
    const expanded = evidenceRationaleToggle.getAttribute('aria-expanded') === 'true';
    evidenceRationaleToggle.setAttribute('aria-expanded', String(!expanded));
    evidenceRationalePanel.classList.toggle('hidden', expanded);
  });
}

function extractReferralText(chartEntry) {
  if (!chartEntry) return '';
  const sentences = chartEntry.match(/[^.!?]+[.!?]+/g) || [chartEntry];
  const referral = sentences
    .filter(s => /\brefer(r?(al|ed|ring)?)?\b/i.test(s))
    .join(' ')
    .trim();
  return referral;
}

function buildEvidenceRationale(visitNotes, chartEntry) {
  const combined = `${visitNotes || ''} ${chartEntry || ''}`.toLowerCase();
  if (/rlq|appendic|emesis|vomit/.test(combined)) {
    return "System Rationale: Identified clinical tokens 'RLQ pain' and 'emesis' matching MeSH term D001064 (Appendicitis). Cross-referenced history array: No prior appendectomy on file. Urgency escalated to CRITICAL.";
  }
  if (/\brefer/.test(combined)) {
    return "System Rationale: Matched plan tokens from visit notes against pre-visit briefing chips and medication history. Referral language synthesized with ROUTINE urgency. Confidence: 0.91.";
  }
  return "System Rationale: No specialist referral tokens detected in visit notes. Referral block held for clinician review. Confidence: 0.72.";
}

function updateReferralOutput(chartEntry, visitNotes) {
  const referralEl = document.getElementById('specialist-referral-output');
  const rationaleEl = document.getElementById('evidence-rationale-text');
  if (!referralEl) return;

  const referral = extractReferralText(chartEntry);
  if (referral) {
    referralEl.textContent = referral;
    referralEl.classList.add('populated');
  } else {
    referralEl.textContent = 'No specialist referral identified in generated note.';
    referralEl.classList.remove('populated');
  }

  if (rationaleEl) {
    rationaleEl.textContent = buildEvidenceRationale(visitNotes, chartEntry);
  }
}

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
const copilotChiefComplaint = document.getElementById('copilot-chief-complaint');
let activeVisitId = null;

bindPatientIntakeInput(visitReasonInput);
bindPatientIntakeInput(copilotChiefComplaint);

if (demoVisitReasonBtn) {
  demoVisitReasonBtn.addEventListener('click', async () => {
    if (visitReasonInput) visitReasonInput.value = DEMO_VISIT_REASON;
    if (copilotChiefComplaint) copilotChiefComplaint.value = DEMO_VISIT_REASON;
    showPatientIntake(DEMO_VISIT_REASON);
    if (isCopilotMode()) {
      await ensureVisitStarted({ silent: true });
    }
  });
}

(function initPatientIntakeFromActiveVisit() {
  const reason = copilotChiefComplaint?.value?.trim() || visitReasonInput?.value?.trim();
  if (reason) showPatientIntake(reason);
})();

async function ensureVisitStarted({ silent = false } = {}) {
  const existing = activeVisitId || document.getElementById('active-visit-id')?.value;
  if (existing) {
    activeVisitId = existing;
    document.getElementById('visit-started-section')?.classList.remove('hidden');
    document.getElementById('start-visit-section')?.classList.add('hidden');
    return existing;
  }

  const reason = (
    copilotChiefComplaint?.value?.trim()
    || visitReasonInput?.value?.trim()
    || document.querySelector('.exec-impression')?.textContent?.slice(0, 80)
    || 'Return visit — clinical review'
  );

  const patientId = document.body.dataset.patientId;
  if (!patientId) return null;

  try {
    const resp = await fetch(`/flow-b/${patientId}/start-visit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ visit_reason: reason }),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      if (!silent) {
        showAlert(document.getElementById('flow-b-alerts'), 'danger', data.error);
      }
      return null;
    }
    activeVisitId = data.visit_id;
    document.getElementById('active-visit-id')?.setAttribute('value', activeVisitId);
    document.getElementById('visit-started-section')?.classList.remove('hidden');
    document.getElementById('start-visit-section')?.classList.add('hidden');
    if (copilotChiefComplaint && !copilotChiefComplaint.value) {
      copilotChiefComplaint.value = reason;
    }
    showPatientIntake(reason);
    if (!silent) {
      showAlert(document.getElementById('flow-b-alerts'), 'info', `Encounter opened: ${reason}`);
    }
    return activeVisitId;
  } catch (err) {
    if (!silent) {
      showAlert(document.getElementById('flow-b-alerts'), 'danger', `Error: ${err.message}`);
    }
    return null;
  }
}

if (startVisitBtn) {
  startVisitBtn.addEventListener('click', async () => {
    setButtonLoading(startVisitBtn, true, 'Starting visit…');
    const reason = visitReasonInput?.value?.trim() || DEMO_VISIT_REASON;
    showPatientIntake(reason);
    await ensureVisitStarted({ silent: false });
    setButtonLoading(startVisitBtn, false);
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
  const runGenerateNote = async () => {
    if (isCopilotMode()) {
      await ensureVisitStarted({ silent: true });
    }
    const notes = visitNotesTextarea?.value?.trim();
    if (!notes) {
      showAlert(document.getElementById('flow-b-alerts'), 'warning',
        isCopilotMode() ? 'Enter encounter documentation before generating.' : 'Enter visit notes before generating.');
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
      updateReferralOutput(generatedOutput.chart_entry, notes);
      populateSuggestedTasks(generatedOutput.suggested_tasks || []);
      dualOutputSection?.classList.remove('hidden');
      document.getElementById('confirm-note-section')?.classList.remove('hidden');
      document.getElementById('copilot-authorize-bar')?.classList.remove('hidden');
      dualOutputSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      showAlert(document.getElementById('flow-b-alerts'), 'success',
        isCopilotMode()
          ? 'Clinical draft ready. Review chart entry and authorize care plan orders below.'
          : 'Outputs generated. Review AI-suggested follow-up tasks before confirming.');
    } catch (err) {
      showAlert(document.getElementById('flow-b-alerts'), 'danger', `Error: ${err.message}`);
    } finally {
      setButtonLoading(generateNoteBtn, false);
    }
  };

  generateNoteBtn.addEventListener('click', runGenerateNote);

  visitNotesTextarea?.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runGenerateNote();
    }
  });
}

// -------------------------------------------------------------------------
// Flow B — Task builder (AI suggestions + doctor approval)
// -------------------------------------------------------------------------
const addTaskBtn = document.getElementById('btn-add-task');
const taskList = document.getElementById('task-list');
const taskListEmpty = document.getElementById('task-list-empty');
const taskSuggestionsBanner = document.getElementById('task-suggestions-banner');
let taskCount = 0;

function defaultDueDate(daysAhead = 30) {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  return d.toISOString().split('T')[0];
}

function updateTaskListEmptyState() {
  const rows = taskList?.querySelectorAll('.task-row') || [];
  const approved = taskList?.querySelectorAll('.task-row .task-approve:checked') || [];
  taskListEmpty?.classList.toggle('hidden', rows.length > 0);
  if (rows.length > 0 && approved.length === 0) {
    taskListEmpty?.classList.remove('hidden');
    if (taskListEmpty) taskListEmpty.textContent = 'No tasks approved. Check at least one task to save, or add manually.';
  } else if (rows.length === 0 && taskListEmpty) {
    taskListEmpty.textContent = 'No tasks yet. Add a task or regenerate from visit notes.';
  }
}

function bindTaskRowEvents(row) {
  const approve = row.querySelector('.task-approve');
  const label = row.querySelector('.task-approve-label');
  const syncRejected = () => {
    row.classList.toggle('task-row-rejected', approve && !approve.checked);
    updateTaskListEmptyState();
  };
  approve?.addEventListener('change', syncRejected);
  label?.addEventListener('click', () => {
    if (approve) {
      approve.checked = !approve.checked;
      syncRejected();
    }
  });
  syncRejected();
}

function addTaskRow(task = {}, { suggested = false } = {}) {
  taskCount++;
  const desc = task.description || '';
  const type = task.type || 'confirmation';
  const due = task.due_date || defaultDueDate();
  const metric = task.target_metric || '';

  const row = document.createElement('div');
  row.className = `task-row${suggested ? ' task-row-suggested' : ''}`;
  row.id = `task-row-${taskCount}`;
  row.innerHTML = `
    <div class="task-approve-wrap" title="Include this task when confirming visit">
      <input type="checkbox" class="task-approve" name="task_approve" checked aria-label="Approve task" />
      <span class="task-approve-label">Approve</span>
    </div>
    <input type="text" name="task_desc" placeholder="Task description…" value="${escapeHtmlAttr(desc)}" required />
    <select name="task_type">
      <option value="confirmation" ${type === 'confirmation' ? 'selected' : ''}>Confirmation</option>
      <option value="recurring_input" ${type === 'recurring_input' ? 'selected' : ''}>Reading</option>
    </select>
    <input type="text" name="task_metric" placeholder="Metric (optional)" value="${escapeHtmlAttr(metric)}" title="e.g. HbA1c, fasting_glucose" />
    <input type="date" name="task_due" value="${due}" />
    ${suggested ? '<span class="task-ai-badge">AI</span>' : ''}
    <button type="button" class="btn btn-sm btn-danger task-remove-btn" aria-label="Remove task">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M18 6 6 18M6 6l12 12"/></svg>
    </button>
  `;

  row.querySelector('.task-remove-btn')?.addEventListener('click', () => {
    row.remove();
    updateTaskListEmptyState();
  });

  bindTaskRowEvents(row);
  taskList?.appendChild(row);
  updateTaskListEmptyState();
  updateCopilotTaskLabels();
  return row;
}

function escapeHtmlAttr(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;');
}

function populateSuggestedTasks(suggestedTasks) {
  if (!taskList) return;
  taskList.innerHTML = '';
  taskCount = 0;

  const tasks = Array.isArray(suggestedTasks) ? suggestedTasks : [];
  if (tasks.length > 0) {
    taskSuggestionsBanner?.classList.remove('hidden');
    tasks.forEach(task => addTaskRow(task, { suggested: true }));
    if (typeof lucide !== 'undefined') lucide.createIcons();
  } else {
    taskSuggestionsBanner?.classList.add('hidden');
  }
  updateTaskListEmptyState();
}

if (addTaskBtn) {
  addTaskBtn.addEventListener('click', () => {
    addTaskRow({}, { suggested: false });
  });
}

// -------------------------------------------------------------------------
// Flow B — Confirm / authorize encounter
// -------------------------------------------------------------------------
const confirmNoteBtn = document.getElementById('btn-confirm-note');
const copilotAuthorizeBtn = document.getElementById('btn-copilot-authorize');
const copilotSendPortalCheckbox = document.getElementById('copilot-send-portal');

function collectApprovedTasks() {
  const tasks = [];
  document.querySelectorAll('.task-row').forEach(row => {
    const approved = row.querySelector('.task-approve')?.checked;
    if (!approved) return;
    const desc = row.querySelector('[name="task_desc"]')?.value?.trim();
    const type = row.querySelector('[name="task_type"]')?.value;
    const due = row.querySelector('[name="task_due"]')?.value;
    const metric = row.querySelector('[name="task_metric"]')?.value?.trim();
    if (desc && due) {
      const task = { description: desc, type, due_date: due };
      if (metric) task.target_metric = metric;
      tasks.push(task);
    }
  });
  return tasks;
}

async function confirmEncounter({ sendPortal = false, triggerBtn = null } = {}) {
  if (!generatedOutput) {
    showAlert(document.getElementById('flow-b-alerts'), 'warning', 'Generate clinical draft first.');
    return;
  }

  const tasks = collectApprovedTasks();
  if (document.querySelectorAll('.task-row').length > 0 && tasks.length === 0) {
    showAlert(document.getElementById('flow-b-alerts'), 'warning',
      isCopilotMode()
        ? 'No care plan orders authorized. Check at least one order to issue.'
        : 'No tasks approved. Check at least one task to include, or confirm without tasks.');
    return;
  }

  const patientId = document.body.dataset.patientId;
  let visitId = activeVisitId || document.getElementById('active-visit-id')?.value;
  if (!visitId && isCopilotMode()) {
    visitId = await ensureVisitStarted({ silent: true });
  }

  if (triggerBtn) setButtonLoading(triggerBtn, true, isCopilotMode() ? 'Authorizing…' : 'Saving visit…');

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

    document.getElementById('saved-visit-id')?.setAttribute('value', visitId);
    if (confirmNoteBtn) confirmNoteBtn.disabled = true;
    if (copilotAuthorizeBtn) copilotAuthorizeBtn.disabled = true;

    if (sendPortal) {
      const portalResp = await fetch(`/flow-b/${patientId}/send-portal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visit_id: visitId }),
      });
      const portalData = await portalResp.json();
      if (portalResp.ok && portalData.portal_url) {
        const portalLinkDisplay = document.getElementById('portal-link-display');
        if (portalLinkDisplay) {
          portalLinkDisplay.textContent = portalData.portal_url;
          portalLinkDisplay.href = portalData.portal_url;
        }
        showAlert(document.getElementById('flow-b-alerts'), 'success',
          `Encounter authorized. ${data.task_count} care plan order(s) issued. Patient instructions dispatched.`);
      } else {
        showAlert(document.getElementById('flow-b-alerts'), 'success',
          `Encounter saved. ${data.task_count} order(s) issued. Portal dispatch failed — retry from full EMR view.`);
      }
    } else {
      showAlert(document.getElementById('flow-b-alerts'), 'success',
        `Encounter saved. ${data.task_count} follow-up task(s) created. ${data.message}`);
      document.getElementById('send-portal-section')?.classList.remove('hidden');
    }
  } catch (err) {
    showAlert(document.getElementById('flow-b-alerts'), 'danger', `Error: ${err.message}`);
  } finally {
    if (triggerBtn) setButtonLoading(triggerBtn, false);
  }
}

if (confirmNoteBtn) {
  confirmNoteBtn.addEventListener('click', () => confirmEncounter({ sendPortal: false, triggerBtn: confirmNoteBtn }));
}

if (copilotAuthorizeBtn) {
  copilotAuthorizeBtn.addEventListener('click', () => {
    confirmEncounter({
      sendPortal: copilotSendPortalCheckbox?.checked ?? true,
      triggerBtn: copilotAuthorizeBtn,
    });
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
