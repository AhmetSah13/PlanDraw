import { tr } from "../content/tr";

interface CompileResultPanelProps {
  ok: boolean | null;
  error: string | null;
  commandCount: number;
  strokeCount: number;
  penSafe: boolean;
}

export function CompileResultPanel({
  ok,
  error,
  commandCount,
  strokeCount,
  penSafe,
}: CompileResultPanelProps) {
  if (ok === null) {
    return (
      <section className="panel">
        <h2 className="text-lg font-semibold text-slate-900">{tr.compile.title}</h2>
        <p className="mt-3 text-sm text-slate-500">{tr.compile.idle}</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2 className="text-lg font-semibold text-slate-900">{tr.compile.title}</h2>

      {ok ? (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
          <p className="font-semibold">{tr.compile.success}</p>
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">
          <p className="font-semibold">{tr.compile.error}</p>
          {error ? <p className="mt-1 text-sm">{error}</p> : null}
        </div>
      )}

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-slate-50 p-3">
          <dt className="text-slate-500">{tr.compile.commandCount}</dt>
          <dd className="text-xl font-semibold text-slate-900">{commandCount}</dd>
        </div>
        <div className="rounded-lg bg-slate-50 p-3">
          <dt className="text-slate-500">{tr.compile.strokeCount}</dt>
          <dd className="text-xl font-semibold text-slate-900">{strokeCount}</dd>
        </div>
      </dl>

      <div
        className={`mt-4 rounded-xl border p-3 text-sm ${
          penSafe
            ? "border-emerald-200 bg-emerald-50/60 text-emerald-900"
            : "border-amber-200 bg-amber-50/60 text-amber-900"
        }`}
      >
        <p className="font-semibold">{tr.compile.penSafe}</p>
        <p className="mt-1">{penSafe ? tr.compile.penSafeOk : tr.compile.penSafeWarn}</p>
      </div>
    </section>
  );
}
