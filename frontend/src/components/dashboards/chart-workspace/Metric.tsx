export function Metric({ label, value, title }: { label: string; value: string | number; title?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-2" title={title}>
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}
