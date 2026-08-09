import { Badge } from "@/components/ui/Badge";

interface ISMParamsData {
  EDT: number | null;
  T20: number | null;
  T30: number | null;
  C80: number;
  C50: number;
  D50: number;
  Ts: number;
  ITDG: number | null;
  flutter_echo: { detected: boolean; frequency: number | null };
  [key: string]: unknown;
}

export function ISMParams({ params }: { params: ISMParamsData }) {
  const paramRows = [
    { label: "EDT", value: params.EDT, unit: "s", desc: "Early Decay Time" },
    { label: "T20", value: params.T20, unit: "s", desc: "Tiempo de reverberación (20 dB)" },
    { label: "T30", value: params.T30, unit: "s", desc: "Tiempo de reverberación (30 dB)" },
    { label: "C80", value: params.C80, unit: "dB", desc: "Claridad musical" },
    { label: "C50", value: params.C50, unit: "dB", desc: "Claridad del habla" },
    { label: "D50", value: params.D50, unit: "%", desc: "Definición" },
    { label: "Ts", value: params.Ts, unit: "ms", desc: "Tiempo centro" },
    { label: "ITDG", value: params.ITDG ?? 0, unit: "ms", desc: "Initial Time Delay Gap" },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-700">
          Parámetros ISO 3382-1
        </h3>
        <Badge variant="info">PAID</Badge>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {paramRows.map((p) => (
          <div key={p.label} className="rounded-lg border border-gray-200 bg-white p-2 text-center shadow-sm">
            <p className="text-xs text-gray-600">{p.label}</p>
            <p className="text-lg font-bold text-indigo-600">
              {typeof p.value === "number" ? p.value.toFixed(2) : "—"}
              <span className="ml-0.5 text-xs font-normal text-gray-600">{p.unit}</span>
            </p>
            <p className="text-[10px] text-gray-600">{p.desc}</p>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className="text-gray-500">Flutter echo:</span>
        {params.flutter_echo.detected ? (
          <Badge variant="danger">
            Detectado ~{params.flutter_echo.frequency?.toFixed(0)} Hz
          </Badge>
        ) : (
          <Badge variant="success">No detectado</Badge>
        )}
      </div>
    </div>
  );
}
