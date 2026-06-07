import { tr } from "../content/tr";

interface RobotControlPanelProps {
  hasCommands: boolean;
  busy: boolean;
  simulationActive: boolean;
  onDryRun: () => void;
  onSimulate: () => void;
  onLive: () => void;
  onLiveStop: () => void;
  onSimStop: () => void;
}

export function RobotControlPanel({
  hasCommands,
  busy,
  simulationActive,
  onDryRun,
  onSimulate,
  onLive,
  onLiveStop,
  onSimStop,
}: RobotControlPanelProps) {
  const disabled = !hasCommands || busy;

  return (
    <section className="panel">
      <h2 className="text-lg font-semibold text-slate-900">{tr.robot.title}</h2>
      {!hasCommands ? (
        <p className="mt-2 text-sm text-slate-500">{tr.robot.needsCommands}</p>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <button type="button" className="btn-secondary" disabled={disabled} onClick={onDryRun}>
          {tr.robot.dryRun}
        </button>
        <button type="button" className="btn-secondary" disabled={disabled} onClick={onSimulate}>
          {tr.robot.simulate}
        </button>
        <button type="button" className="btn-primary sm:col-span-2" disabled={disabled} onClick={onLive}>
          {tr.robot.live}
        </button>
      </div>

      <div className="mt-6 rounded-2xl border-2 border-red-300 bg-red-50 p-4">
        <button
          type="button"
          className="btn-danger w-full text-base"
          disabled={busy}
          onClick={onLiveStop}
        >
          {tr.robot.stop}
        </button>
        <p className="mt-2 text-center text-xs text-red-800">{tr.robot.stopHint}</p>
      </div>

      {simulationActive ? (
        <button type="button" className="btn-warning mt-3 w-full" disabled={busy} onClick={onSimStop}>
          {tr.robot.simStop}
        </button>
      ) : null}
    </section>
  );
}
