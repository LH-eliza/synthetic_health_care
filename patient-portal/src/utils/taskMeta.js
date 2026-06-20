export const TASK_META = {
  checkbox: {
    label: 'Confirm',
    action: 'Check the box when you’ve done this',
    cta: 'Mark complete',
  },
  file_upload: {
    label: 'Upload',
    action: 'Attach a photo or PDF of your document',
    cta: 'Choose file',
  },
  bp_log: {
    label: 'Log reading',
    action: 'Enter your blood pressure numbers',
    cta: 'Save reading',
  },
  notes_textarea: {
    label: 'Notes',
    action: 'Tell your doctor about another visit or attach a file',
    cta: 'Save notes',
  },
};

export function getTaskMeta(type) {
  return TASK_META[type] || TASK_META.checkbox;
}
