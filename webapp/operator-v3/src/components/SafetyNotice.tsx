import { ShieldAlert } from "lucide-react";
import { tr } from "../content/tr";

export function SafetyNotice() {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/5 px-4 py-3">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
      <p className="text-xs leading-relaxed text-amber-100/90">{tr.safety.banner}</p>
    </div>
  );
}
