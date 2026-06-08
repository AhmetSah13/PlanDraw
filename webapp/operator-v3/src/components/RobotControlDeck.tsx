import { useState } from "react";
import {
  AlertTriangle,
  FileCode2,
  Play,
  Radio,
  Send,
  Square,
  Upload,
} from "lucide-react";
import { tr } from "../content/tr";
import type { ActionFeedback } from "../lib/workflowState";
import { ActionFeedbackCard } from "./ActionFeedbackCard";
import { GlowCard } from "./GlowCard";

interface RobotControlDeckProps {
  hasCommands: boolean;
  busy: boolean;
  simulationActive: boolean;
  selectedFileName: string | null;
  actionFeedback: ActionFeedback | null;
  canCompile: boolean;
  canDryRun: boolean;
  canSimulate: boolean;
  canLive: boolean;
  compileReason: string | null;
  dryRunReason: string | null;
  simulateReason: string | null;
  liveReason: string | null;
  compileAnchorId?: string;
  robotAnchorId?: string;
  compileAnchorRef?: (el: HTMLDivElement | null) => void;
  robotAnchorRef?: (el: HTMLDivElement | null) => void;
  onFileSelect: (file: File) => void;
  onCompile: () => void;
  onDryRun: () => void;
  onSimulate: () => void;
  onLive: () => void;
  onLiveStop: () => void;
  onSimStop: () => void;
}

export function RobotControlDeck({
  hasCommands,
  busy,
  simulationActive,
  selectedFileName,
  actionFeedback,
  canCompile,
  canDryRun,
  canSimulate,
  canLive,
  compileReason,
  dryRunReason,
  simulateReason,
  liveReason,
  compileAnchorId,
  robotAnchorId,
  compileAnchorRef,
  robotAnchorRef,
  onFileSelect,
  onCompile,
  onDryRun,
  onSimulate,
  onLive,
  onLiveStop,
  onSimStop,
}: RobotControlDeckProps) {
  const [liveConfirmOpen, setLiveConfirmOpen] = useState(false);

  return (
    <GlowCard title={tr.control.title} accent>
      <p className="mb-4 text-xs text-cyan-200/70">{tr.control.penSafeNote}</p>

      <div id={compileAnchorId} ref={compileAnchorRef} className="scroll-mt-4">
        <label className="btn-ghost mb-3 w-full cursor-pointer">
          <Upload className="h-4 w-4" />
          {tr.control.upload}
          <input
            type="file"
            accept=".dxf,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFileSelect(f);
              e.target.value = "";
            }}
          />
        </label>
        {selectedFileName ? (
          <p className="mb-4 truncate text-xs text-slate-500">{selectedFileName}</p>
        ) : null}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <button type="button" className="btn-cyan" disabled={!canCompile} onClick={onCompile}>
          <FileCode2 className="h-4 w-4" />
          {busy ? tr.control.busy : tr.control.compile}
        </button>
        <button type="button" className="btn-ghost" disabled={!canDryRun} onClick={onDryRun}>
          <Play className="h-4 w-4" />
          {tr.control.dryRun}
        </button>
        <button type="button" className="btn-ghost" disabled={!canSimulate} onClick={onSimulate}>
          <Radio className="h-4 w-4" />
          {tr.control.simulate}
        </button>
        <button
          type="button"
          className="btn-cyan border-amber-500/40 bg-amber-500/10 text-amber-100 hover:border-amber-400/50"
          disabled={!canLive}
          onClick={() => setLiveConfirmOpen(true)}
        >
          <Send className="h-4 w-4" />
          {tr.control.live}
        </button>
      </div>

      {[compileReason, dryRunReason, simulateReason, liveReason].filter(Boolean).length ? (
        <div className="mt-3 space-y-1 text-[11px] leading-snug text-slate-500">
          {compileReason ? <p>{tr.control.compile}: {compileReason}</p> : null}
          {dryRunReason ? <p>{tr.control.dryRun}: {dryRunReason}</p> : null}
          {simulateReason ? <p>{tr.control.simulate}: {simulateReason}</p> : null}
          {liveReason ? <p>{tr.control.live}: {liveReason}</p> : null}
        </div>
      ) : null}

      <p className="mt-2 text-[11px] leading-snug text-slate-500">{tr.control.dryRunHint}</p>
      <p className="mt-1 text-[11px] leading-snug text-slate-600">{tr.control.simulateHint}</p>

      <ActionFeedbackCard feedback={actionFeedback} />

      {!hasCommands ? (
        <p className="mt-3 text-xs text-slate-600">{tr.control.needsPlan}</p>
      ) : null}

      <div id={robotAnchorId} ref={robotAnchorRef} className="scroll-mt-4">
        <p className="mt-4 flex items-start gap-2 text-[11px] text-amber-400/80">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {tr.control.liveNote}
        </p>

        <div className="mt-6 rounded-2xl border-2 border-red-500/40 bg-red-950/30 p-4">
          <button type="button" className="btn-stop w-full py-3 text-base" disabled={busy} onClick={onLiveStop}>
            <Square className="h-5 w-5 fill-current" />
            {tr.control.stop}
          </button>
          <p className="mt-2 text-center text-[10px] text-red-300/70">{tr.control.stopNote}</p>
        </div>

        {simulationActive ? (
          <button type="button" className="btn-ghost mt-3 w-full" disabled={busy} onClick={onSimStop}>
            {tr.control.simStop}
          </button>
        ) : null}
      </div>

      {liveConfirmOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="glass-panel max-w-md border-amber-500/30 p-6 shadow-glow">
            <h3 className="text-lg font-bold text-white">{tr.control.liveConfirmTitle}</h3>
            <p className="mt-3 text-sm text-slate-400">{tr.control.liveConfirmBody}</p>
            <div className="mt-6 flex gap-3">
              <button type="button" className="btn-ghost flex-1" onClick={() => setLiveConfirmOpen(false)}>
                {tr.control.cancel}
              </button>
              <button
                type="button"
                className="btn-cyan flex-1 border-amber-500/50"
                onClick={() => {
                  setLiveConfirmOpen(false);
                  onLive();
                }}
              >
                {tr.control.liveConfirmAction}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </GlowCard>
  );
}
