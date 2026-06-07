import type { ReactNode } from "react";
import type { ActiveMode, MissionSection } from "../content/tr";
import { CommandHeader } from "./CommandHeader";
import { MissionRail } from "./MissionRail";

interface MissionShellProps {
  children: ReactNode;
  activeSection: MissionSection;
  onNavigate: (section: MissionSection) => void;
  backendOnline: boolean;
  robotLabel: string;
  activeMode: ActiveMode;
  lastUpdate: string;
  onStop: () => void;
  stopBusy: boolean;
}

export function MissionShell({
  children,
  activeSection,
  onNavigate,
  backendOnline,
  robotLabel,
  activeMode,
  lastUpdate,
  onStop,
  stopBusy,
}: MissionShellProps) {
  return (
    <div className="flex min-h-screen">
      <MissionRail active={activeSection} onNavigate={onNavigate} />
      <div className="flex min-w-0 flex-1 flex-col">
        <CommandHeader
          backendOnline={backendOnline}
          robotLabel={robotLabel}
          activeMode={activeMode}
          lastUpdate={lastUpdate}
          onStop={onStop}
          stopBusy={stopBusy}
        />
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
