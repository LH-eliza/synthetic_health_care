export function isTaskCompleteForProgress(task) {
  if (task.isRecurring) return Boolean(task.loggedInPeriod);
  return Boolean(task.isCompleted);
}

export function frequencyLabel(frequency) {
  if (frequency === 'daily') return 'Daily';
  if (frequency === 'weekly') return 'Weekly';
  return 'One-time';
}

export function periodDoneLabel(task) {
  if (task.frequency === 'weekly') return 'Done this week';
  if (task.frequency === 'daily') return 'Done for today';
  return 'Completed';
}
