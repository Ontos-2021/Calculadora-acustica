export function MetricCard({
  label,
  value,
  unit,
  sublabel,
  color = "text-foreground",
}: {
  label: string;
  value: string | number;
  unit?: string;
  sublabel?: string;
  color?: string;
}) {
  return (
    <div className="rounded-[var(--radius-card)] border bg-surface p-4 text-left shadow-[var(--shadow-panel)]">
      <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">
        {label}
      </p>
      <p className={`data-value mt-2 text-2xl font-bold tracking-tight ${color}`}>
        {value}
        {unit && <span className="ml-1 text-sm font-medium text-muted">{unit}</span>}
      </p>
      {sublabel && <p className="mt-1 text-xs text-muted">{sublabel}</p>}
    </div>
  );
}
