export function MetricCard({
  label,
  value,
  unit,
  sublabel,
  color = "text-gray-800",
}: {
  label: string;
  value: string | number;
  unit?: string;
  sublabel?: string;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 text-center shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <p className={`mt-1 text-3xl font-bold ${color}`}>
        {value}
        {unit && <span className="ml-1 text-lg font-normal text-gray-400">{unit}</span>}
      </p>
      {sublabel && <p className="mt-0.5 text-xs text-gray-400">{sublabel}</p>}
    </div>
  );
}
