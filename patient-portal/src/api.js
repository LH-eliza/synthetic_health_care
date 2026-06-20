import demoData from './demoData.json';

const TOKEN = window.__PORTAL_TOKEN__ || 'demo';
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';

let demoState = structuredClone(demoData);

function demoTasksClone() {
  return structuredClone(demoState.tasks);
}

export async function fetchPortalData() {
  if (DEMO_MODE) {
    return structuredClone(demoState);
  }
  const res = await fetch(`/p/${TOKEN}/api/data`);
  if (!res.ok) throw new Error('Failed to load portal data');
  return res.json();
}

export async function submitTask(taskId, body) {
  if (DEMO_MODE) {
    const tasks = demoTasksClone();
    const idx = tasks.findIndex((t) => t.id === taskId);
    if (idx >= 0) {
      const task = tasks[idx];
      if (task.isRecurring) {
        task.loggedInPeriod = true;
        task.isCompleted = true;
        task.streak = (task.streak || 0) + 1;
        const today = demoState.progressCalendar?.today || new Date().toISOString().slice(0, 10);
        task.loggedDates = [...(task.loggedDates || []), today];
        if (body.type === 'bp_log' && body.payload?.reading) {
          task.payload = [...(task.payload || []), body.payload.reading];
        }
      } else {
        task.isCompleted = true;
        if (body.payload?.filename) task.payload = body.payload.filename;
      }
      demoState.tasks = tasks;
    }
    return { success: true, tasks: demoTasksClone(), progressCalendar: demoState.progressCalendar };
  }
  const res = await fetch(`/p/${TOKEN}/api/task/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to submit task');
  return res.json();
}

export async function sendToDoctor() {
  if (DEMO_MODE) {
    return { success: true, message: 'Summary sent to your care team.' };
  }
  const res = await fetch(`/p/${TOKEN}/api/send`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to send');
  return res.json();
}

export { TOKEN };
