import { tr } from "../content/tr";

interface CommandLogPanelProps {
  commandsPreview: string;
  activityLog: string[];
  lastError: string | null;
  lastSuccess: string | null;
}

export function CommandLogPanel({
  commandsPreview,
  activityLog,
  lastError,
  lastSuccess,
}: CommandLogPanelProps) {
  return (
    <section className="panel flex h-full flex-col">
      <h2 className="text-lg font-semibold text-slate-900">{tr.log.title}</h2>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-red-100 bg-red-50/50 p-3 text-sm">
          <p className="font-medium text-red-800">{tr.log.lastError}</p>
          <p className="mt-1 text-red-700">{lastError ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-3 text-sm">
          <p className="font-medium text-emerald-800">{tr.log.lastSuccess}</p>
          <p className="mt-1 text-emerald-700">{lastSuccess ?? "—"}</p>
        </div>
      </div>

      <div className="mt-4 min-h-[140px] flex-1 overflow-auto rounded-xl bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100">
        {commandsPreview ? (
          <pre className="whitespace-pre-wrap">{commandsPreview}</pre>
        ) : (
          <p className="text-slate-400">{tr.log.empty}</p>
        )}
      </div>

      {activityLog.length > 0 ? (
        <ul className="mt-3 max-h-28 space-y-1 overflow-auto text-xs text-slate-600">
          {activityLog.map((line, i) => (
            <li key={`${i}-${line.slice(0, 24)}`}>• {line}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
