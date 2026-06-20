const TOKEN = window.__PORTAL_TOKEN__ || 'demo';

export async function fetchPortalData() {
  const res = await fetch(`/p/${TOKEN}/api/data`);
  if (!res.ok) throw new Error('Failed to load portal data');
  return res.json();
}

export async function submitTask(taskId, body) {
  const res = await fetch(`/p/${TOKEN}/api/task/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to submit task');
  return res.json();
}

export async function sendToDoctor() {
  const res = await fetch(`/p/${TOKEN}/api/send`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to send');
  return res.json();
}

export { TOKEN };
