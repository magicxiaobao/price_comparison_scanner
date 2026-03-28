import type { AnomalyDetail } from "../../types/comparison";

interface AnomalyHighlightProps {
  anomalies: AnomalyDetail[];
}

export function AnomalyHighlight({ anomalies }: AnomalyHighlightProps) {
  if (anomalies.length === 0) return null;

  return (
    <div className="space-y-2 px-4 py-3 bg-slate-50 border-t border-slate-100">
      {anomalies.map((anomaly, idx) => (
        <div key={idx} className="flex items-start gap-2 text-sm">
          {anomaly.blocking ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 mt-0.5 flex-none text-red-500"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 mt-0.5 flex-none text-yellow-500"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
          )}
          <div className="flex-1">
            <span
              className={
                anomaly.blocking
                  ? "font-medium text-red-700"
                  : "font-medium text-yellow-700"
              }
            >
              {anomalyTypeLabel(anomaly.type)}
            </span>
            <span className="text-slate-600 ml-1.5">{anomaly.description}</span>
            {anomaly.affectedSuppliers.length > 0 && (
              <span className="text-slate-400 ml-1.5">
                ({anomaly.affectedSuppliers.join(", ")})
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function anomalyTypeLabel(type: string): string {
  switch (type) {
    case "tax_basis_mismatch":
      return "[含税口径不一致]";
    case "unit_mismatch":
      return "[单位不一致]";
    case "currency_mismatch":
      return "[币种不一致]";
    case "missing_required_field":
      return "[缺少必填字段]";
    default:
      return `[${type}]`;
  }
}
