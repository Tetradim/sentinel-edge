export function formatAge(iso: string | null) {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'unknown';
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m ago`;
}

export function formatElapsedAge(value?: number | null) {
  if (value === null || value === undefined) return '';
  if (value < 1) return 'just now';
  if (value < 60) return `${Math.round(value)}s ago`;
  return `${Math.round(value / 60)}m ago`;
}
