import { Octagon, Radio } from "lucide-react";
import type { ActiveMode } from "../content/tr";
import { tr } from "../content/tr";
import { StatusPill } from "./StatusPill";

interface CommandHeaderProps {
  backendOnline: boolean;
  robotLabel: string;
  activeMode: ActiveMode;
  lastUpdate: string;
  onStop: () => void;
  stopBusy: boolean;
}

const modeLabels: Record<ActiveMode, string> = {
  idle: tr.modes.idle,
  dryRun: tr.modes.dryRun,
  simulation: tr.modes.simulation,
  live: tr.modes.live,
};

export function CommandHeader({
  backendOnline,
  robotLabel,
  activeMode,
  lastUpdate,
  onStop,
  stopBusy,
}: CommandHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/5 bg-command-surface/60 px-6 py-4 backdrop-blur-md">
      <div className="min-w-0">
        <h1 className="text-lg font-bold tracking-tight text-white md:text-xl">
          {tr.brand.hero}
        </h1>
        <p className="mt-0.5 max-w-2xl text-xs text-slate-500">{tr.brand.subtitle}</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <StatusPill
          label={`${tr.header.backend}: ${backendOnline ? tr.telemetry.online : tr.telemetry.offline}`}
          variant={backendOnline ? "emerald" : "red"}
          pulse={backendOnline}
        />
        <StatusPill
          label={`${tr.header.robot}: ${robotLabel}`}
          variant="cyan"
        />
        <StatusPill
          label={`${tr.header.activeMode}: ${modeLabels[activeMode]}`}
          variant={activeMode === "live" ? "amber" : "violet"}
        />
        <span className="hidden text-[10px] text-slate-600 lg:inline">
          {tr.header.lastUpdate}: {lastUpdate}
        </span>
        <button
          type="button"
          className="btn-stop px-3 py-2 text-xs"
          disabled={stopBusy}
          onClick={onStop}
          title={tr.header.stopHint}
        >
          <Octagon className="h-3.5 w-3.5" />
          {tr.header.stop}
        </button>
        <div className="hidden items-center gap-1 text-[10px] text-red-400/80 sm:flex">
          <Radio className="h-3 w-3" />
          {tr.header.stopHint}
        </div>
      </div>
    </header>
  );
}
