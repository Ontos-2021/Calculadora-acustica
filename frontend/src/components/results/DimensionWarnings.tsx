import { Badge } from "@/components/ui/Badge";

export function DimensionWarnings({ warnings }: { warnings: string[] }) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Badge variant="warning">Advertencia de dimensiones</Badge>
      </div>
      <ul className="ml-4 list-disc space-y-1 text-sm text-amber-800">
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </div>
  );
}
