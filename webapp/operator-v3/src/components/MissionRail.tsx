import { motion } from "framer-motion";
import {
  Activity,
  Bot,
  Cpu,
  FileInput,
  Layers,
  ScrollText,
  Zap,
} from "lucide-react";
import type { MissionSection } from "../content/tr";
import { tr } from "../content/tr";
import { cn } from "../lib/cn";

const items: { id: MissionSection; icon: typeof Cpu }[] = [
  { id: "sistem", icon: Cpu },
  { id: "plan", icon: FileInput },
  { id: "derleme", icon: Layers },
  { id: "simulasyon", icon: Activity },
  { id: "robot", icon: Bot },
  { id: "loglar", icon: ScrollText },
];

interface MissionRailProps {
  active: MissionSection;
  onNavigate: (section: MissionSection) => void;
}

export function MissionRail({ active, onNavigate }: MissionRailProps) {
  return (
    <aside className="flex w-[220px] shrink-0 flex-col border-r border-white/5 bg-command-surface/80 backdrop-blur-xl">
      <div className="border-b border-white/5 px-5 py-6">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-500/30 bg-cyan-500/10 shadow-glow-sm">
            <Zap className="h-4 w-4 text-cyan-300" />
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight text-white">{tr.brand.name}</p>
            <p className="text-[10px] uppercase tracking-widest text-cyan-400/80">
              {tr.brand.commandCenter}
            </p>
          </div>
        </div>
        <p className="mt-4 text-[11px] leading-snug text-slate-500">{tr.brand.tagline}</p>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {items.map(({ id, icon: Icon }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onNavigate(id)}
              className={cn(
                "relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
                isActive
                  ? "text-cyan-100"
                  : "text-slate-500 hover:bg-white/5 hover:text-slate-300",
              )}
            >
              {isActive ? (
                <motion.span
                  layoutId="rail-active"
                  className="absolute inset-0 rounded-xl border border-cyan-500/30 bg-cyan-500/10"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                />
              ) : null}
              <Icon className={cn("relative h-4 w-4", isActive && "text-cyan-300")} />
              <span className="relative font-medium">{tr.rail[id]}</span>
            </button>
          );
        })}
      </nav>

      <div className="border-t border-white/5 p-4">
        <p className="text-[10px] text-slate-600">v0.2 · Deneme arayüzü</p>
      </div>
    </aside>
  );
}
