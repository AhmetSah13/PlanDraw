import { Activity, Cable, Cpu, Pen, Shield, Unplug, Wifi } from "lucide-react";
import { tr } from "../content/tr";
import { cn } from "../lib/cn";
import { GlowCard } from "./GlowCard";

type TelemetryValue = "online" | "offline" | "unknown" | "waiting" | "ready" | "disabled" | "verified" | "unverified";

interface TelemetryRow {
  icon: typeof Wifi;
  label: string;
  value: string;
  tone: TelemetryValue;
}

interface TelemetryPanelProps {
  backendOnline: boolean;
  penSafe: boolean | null;
  penSafeKnown: boolean;
  serialMode: string | null;
  lastRobotStatus: string | null;
}

function toneClass(tone: TelemetryValue): string {
  switch (tone) {
    case "online":
    case "verified":
    case "ready":
      return "text-emerald-400";
    case "offline":
      return "text-red-400";
    case "disabled":
    case "waiting":
      return "text-amber-400/90";
    default:
      return "text-slate-500";
  }
}

export function TelemetryPanel({
  backendOnline,
  penSafe,
  penSafeKnown,
  serialMode,
  lastRobotStatus,
}: TelemetryPanelProps) {
  const rows: TelemetryRow[] = [
    {
      icon: Wifi,
      label: tr.telemetry.backend,
      value: backendOnline ? tr.telemetry.online : tr.telemetry.offline,
      tone: backendOnline ? "online" : "offline",
    },
    {
      icon: Cpu,
      label: tr.telemetry.firmware,
      value: tr.telemetry.waiting,
      tone: "waiting",
    },
    {
      icon: Cable,
      label: tr.telemetry.serial,
      value: serialMode ?? tr.telemetry.closed,
      tone: serialMode === "live" ? "ready" : serialMode ? "waiting" : "unknown",
    },
    {
      icon: Shield,
      label: tr.telemetry.penSafe,
      value: !penSafeKnown
        ? tr.telemetry.unverified
        : penSafe
          ? tr.telemetry.verified
          : tr.telemetry.unverified,
      tone: penSafeKnown && penSafe ? "verified" : "waiting",
    },
    {
      icon: Activity,
      label: tr.telemetry.stopReady,
      value: tr.telemetry.ready,
      tone: "ready",
    },
    {
      icon: Unplug,
      label: tr.telemetry.motors,
      value: tr.telemetry.disabled,
      tone: "disabled",
    },
    {
      icon: Pen,
      label: tr.telemetry.pen,
      value: lastRobotStatus?.toLowerCase().includes("down")
        ? tr.telemetry.penDown
        : tr.telemetry.unknown,
      tone: "unknown",
    },
  ];

  return (
    <GlowCard title={tr.telemetry.title} className="h-full">
      <ul className="space-y-3">
        {rows.map((row) => (
          <li
            key={row.label}
            className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-slate-900/40 px-3 py-2.5"
          >
            <div className="flex items-center gap-2.5">
              <row.icon className="h-4 w-4 text-cyan-600/70" />
              <span className="text-xs text-slate-400">{row.label}</span>
            </div>
            <span className={cn("text-xs font-semibold", toneClass(row.tone))}>{row.value}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-[10px] leading-relaxed text-slate-600">{tr.telemetry.motorNote}</p>
    </GlowCard>
  );
}
