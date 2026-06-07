import { useMemo } from "react";
import { Terminal } from "lucide-react";
import { tr } from "../content/tr";
import { parseActivityLogLevel } from "../lib/workflowState";
import { cn } from "../lib/cn";
import { GlowCard } from "./GlowCard";

function colorizeCommandLine(line: string): string {
  const t = line.trim().toUpperCase();
  if (t.startsWith("ERR") || t.includes("ERROR")) return "text-red-400";
  if (t.startsWith("DONE") || t === "OK") return "text-emerald-400";
  if (t.startsWith("PEN")) return "text-cyan-300";
  if (t.startsWith("BEGIN") || t.startsWith("END")) return "text-violet-300";
  if (t.startsWith("MOVE") || t.startsWith("SPEED")) return "text-slate-400";
  return "text-slate-500";
}

function colorizeActivityLog(line: string): string {
  const level = parseActivityLogLevel(line);
  switch (level) {
    case "ERR":
      return "text-red-400";
    case "OK":
      return "text-emerald-400";
    case "SIM":
      return "text-violet-300";
    case "DRY":
      return "text-cyan-300";
    case "INFO":
      return "text-slate-400";
    default:
      return "text-slate-500";
  }
}

interface CommandStreamProps {
  commandsText: string;
  activityLog: string[];
}

export function CommandStream({ commandsText, activityLog }: CommandStreamProps) {
  const lines = useMemo(() => {
    if (!commandsText.trim()) return [];
    const raw = commandsText.split("\n").filter((l) => l.trim());
    return raw.length > 80 ? [...raw.slice(0, 80), `… (+${raw.length - 80} satır)`] : raw;
  }, [commandsText]);

  return (
    <GlowCard title={tr.stream.title} className="flex flex-col">
      {activityLog.length > 0 ? (
        <div className="mb-4 rounded-lg border border-white/5 bg-slate-900/50 p-3">
          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-600">{tr.stream.activity}</p>
          <ul className="max-h-32 space-y-1 overflow-auto font-mono text-[11px] leading-relaxed">
            {activityLog.map((entry, i) => (
              <li key={`${i}-${entry.slice(0, 20)}`} className={cn(colorizeActivityLog(entry))}>
                {entry}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-600">
        <Terminal className="h-3.5 w-3.5" />
        BEGIN → PEN → MOVE → END
      </div>
      <div className="max-h-52 overflow-auto rounded-lg border border-slate-800 bg-[#020617] p-4 font-mono text-xs leading-relaxed shadow-inner">
        {lines.length === 0 ? (
          <p className="text-slate-600">{tr.stream.empty}</p>
        ) : (
          lines.map((line, i) => (
            <div
              key={`${i}-${line.slice(0, 12)}`}
              className={cn("whitespace-pre-wrap", colorizeCommandLine(line))}
            >
              <span className="mr-3 select-none text-slate-700">{String(i + 1).padStart(3, "0")}</span>
              {line}
            </div>
          ))
        )}
      </div>
    </GlowCard>
  );
}
