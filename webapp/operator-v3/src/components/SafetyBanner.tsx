import { tr } from "../content/tr";

export function SafetyBanner() {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <span className="font-semibold">⚠ Güvenlik:</span> {tr.safety.banner}
    </div>
  );
}
