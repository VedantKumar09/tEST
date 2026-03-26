export function normalizeCategoryMetrics(data) {
  if (typeof data === 'number') {
    const pct = Math.max(0, Math.min(100, Math.round(data)));
    return { pct, label: `${pct}%` };
  }

  const total = Number(data?.total ?? 0);
  const correct = Number(data?.correct ?? 0);
  const pctFromPayload = data?.pct;
  const pct = Number.isFinite(pctFromPayload)
    ? Math.max(0, Math.min(100, Math.round(pctFromPayload)))
    : (total > 0 ? Math.round((correct / total) * 100) : 0);

  return { pct, label: `${correct}/${total} (${pct}%)` };
}
