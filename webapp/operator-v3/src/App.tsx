import { useCallback, useEffect, useMemo, useState } from "react";
import { CommandLogPanel } from "./components/CommandLogPanel";
import { CompileResultPanel } from "./components/CompileResultPanel";
import { PlanPreviewPanel } from "./components/PlanPreviewPanel";
import { PlanUploadCard } from "./components/PlanUploadCard";
import { RobotControlPanel } from "./components/RobotControlPanel";
import { SafetyBanner } from "./components/SafetyBanner";
import { StatusCard } from "./components/StatusCard";
import { tr } from "./content/tr";
import {
  analyzeCommands,
  countMoves,
  countStrokes,
  createSimulationJob,
  executeSerial,
  fetchHealth,
  fetchStatus,
  importDxf,
  importPlanJson,
  isPenSafeCommands,
  stopLiveSerial,
  stopSimulationJob,
} from "./services/api";
import type { AnalyzeResponse, ConnectionState } from "./types/api";

function commandsPreview(text: string, maxLines = 40): string {
  const lines = text.split("\n").filter((l) => l.trim());
  if (lines.length <= maxLines) return lines.join("\n");
  return [...lines.slice(0, maxLines), `… (+${lines.length - maxLines} satır)`].join("\n");
}

export default function App() {
  const [backendState, setBackendState] = useState<ConnectionState>("checking");
  const [robotState, setRobotState] = useState<string>(tr.status.unknown);
  const [statusDetail, setStatusDetail] = useState<string>("");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [planName, setPlanName] = useState<string | null>(null);
  const [commandsText, setCommandsText] = useState("");
  const [walls, setWalls] = useState<number[][]>([]);
  const [pathPoints, setPathPoints] = useState<number[][]>([]);
  const [preflight, setPreflight] = useState<AnalyzeResponse | null>(null);

  const [compileOk, setCompileOk] = useState<boolean | null>(null);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [simJobId, setSimJobId] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);
  const [lastRunLabel, setLastRunLabel] = useState<string>(tr.status.waiting);

  const strokeCount = useMemo(
    () => (commandsText ? countStrokes(commandsText) : 0),
    [commandsText],
  );
  const moveCount = useMemo(
    () => (commandsText ? countMoves(commandsText) : 0),
    [commandsText],
  );
  const penSafe = useMemo(
    () => (commandsText ? isPenSafeCommands(commandsText) : false),
    [commandsText],
  );

  const pushLog = useCallback((line: string) => {
    setActivityLog((prev) => [line, ...prev].slice(0, 30));
  }, []);

  const refreshHealth = useCallback(async () => {
    setBackendState("checking");
    try {
      const health = await fetchHealth();
      await fetchStatus();
      setBackendState(health.ok ? "online" : "offline");
      setStatusDetail("FastAPI /health yanıt verdi");
    } catch {
      setBackendState("offline");
      setStatusDetail("Backend kapalı veya erişilemiyor — mock görünüm aktif");
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    const id = window.setInterval(() => void refreshHealth(), 15000);
    return () => window.clearInterval(id);
  }, [refreshHealth]);

  async function handlePrepare() {
    if (!selectedFile) return;
    setBusy(true);
    setCompileError(null);
    pushLog(`Plan hazırlanıyor: ${selectedFile.name}`);

    try {
      const ext = selectedFile.name.split(".").pop()?.toLowerCase();
      const res =
        ext === "json"
          ? await importPlanJson(selectedFile)
          : await importDxf(selectedFile);

      if (!res.ok) {
        throw new Error(res.error ?? "Plan içe aktarılamadı");
      }

      const cmds =
        res.commands_text_optimized ?? res.commands_text_raw ?? res.commands_text ?? "";
      setCommandsText(cmds);
      setWalls(res.walls ?? []);
      setPathPoints(res.raw_path_points ?? []);
      setPlanName(selectedFile.name);
      setCompileOk(true);
      setLastSuccess(`Plan hazır: ${selectedFile.name}`);

      if (cmds) {
        const analysis = await analyzeCommands(cmds, res.walls);
        setPreflight(analysis);
      }

      pushLog("Plan derlemesi tamamlandı");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setCompileOk(false);
      setCompileError(msg);
      setLastError(msg);
      pushLog(`Hata: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function runDryRun() {
    if (!commandsText) return;
    setBusy(true);
    pushLog("Dry-run başlatıldı");
    try {
      const res = await executeSerial(commandsText, {
        dryRun: true,
        walls,
        preflight: preflight ?? undefined,
      });
      setLastRunLabel(`Dry-run: ${res.status}`);
      setRobotState(res.status);
      setLastSuccess(res.message);
      pushLog(res.message);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setLastError(msg);
      pushLog(msg);
    } finally {
      setBusy(false);
    }
  }

  async function runSimulate() {
    if (!commandsText) return;
    setBusy(true);
    pushLog("Simülasyon job oluşturuluyor");
    try {
      const job = await createSimulationJob(commandsText, walls);
      setSimJobId(job.job_id);
      setLastRunLabel(`Simülasyon: ${job.job_id.slice(0, 8)}…`);
      setLastSuccess("Simülasyon job oluşturuldu");
      pushLog(`Job ID: ${job.job_id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setLastError(msg);
      pushLog(msg);
    } finally {
      setBusy(false);
    }
  }

  async function runLive() {
    if (!commandsText) return;
    setBusy(true);
    pushLog("Canlı gönderim isteği");
    try {
      let pf = preflight;
      if (!pf) {
        pf = await analyzeCommands(commandsText, walls);
        setPreflight(pf);
      }
      const res = await executeSerial(commandsText, {
        dryRun: false,
        walls,
        preflight: pf,
      });
      setLastRunLabel(`Canlı: ${res.status}`);
      setRobotState(res.status);
      setLastSuccess(res.message);
      pushLog(res.message);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setLastError(msg);
      pushLog(msg);
    } finally {
      setBusy(false);
    }
  }

  async function runLiveStop() {
    setBusy(true);
    pushLog("Canlı STOP gönderiliyor");
    try {
      const res = await stopLiveSerial();
      setRobotState(res.stopped ? "Durduruldu" : res.status);
      setLastSuccess(res.message);
      pushLog(res.message);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setLastError(msg);
      pushLog(msg);
    } finally {
      setBusy(false);
    }
  }

  async function runSimStop() {
    if (!simJobId) return;
    setBusy(true);
    try {
      await stopSimulationJob(simJobId);
      setSimJobId(null);
      setLastSuccess("Simülasyon durduruldu");
      pushLog("Simülasyon job stop");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setLastError(msg);
    } finally {
      setBusy(false);
    }
  }

  const backendVariant =
    backendState === "online" ? "success" : backendState === "offline" ? "error" : "info";

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-brand">
              {tr.app.badge}
            </p>
            <h1 className="text-2xl font-bold text-slate-900">{tr.app.title}</h1>
            <p className="text-sm text-slate-600">{tr.app.subtitle}</p>
          </div>
          <div className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
            Backend:{" "}
            <span className="font-semibold text-slate-900">
              {backendState === "online"
                ? tr.status.online
                : backendState === "offline"
                  ? tr.status.offline
                  : tr.status.checking}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
        <SafetyBanner />

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatusCard
            title={tr.dashboard.backend}
            value={
              backendState === "online"
                ? tr.status.online
                : backendState === "offline"
                  ? tr.status.offline
                  : tr.status.checking
            }
            detail={statusDetail}
            variant={backendVariant}
          />
          <StatusCard
            title={tr.dashboard.robot}
            value={robotState}
            detail="Serial / execute_serial durumu"
            variant={robotState.includes("sent") || robotState.includes("dry") ? "info" : "neutral"}
          />
          <StatusCard
            title={tr.dashboard.plan}
            value={compileOk ? tr.status.ready : tr.status.waiting}
            detail={planName ?? "Dosya bekleniyor"}
            variant={compileOk ? "success" : "neutral"}
          />
          <StatusCard
            title={tr.dashboard.safety}
            value={penSafe ? "Pen-safe OK" : "Kontrol gerekli"}
            variant={penSafe ? "success" : "warning"}
          />
          <StatusCard
            title={tr.dashboard.lastRun}
            value={lastRunLabel}
            detail={lastSuccess ?? undefined}
            variant="info"
          />
        </section>

        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-4">
            <PlanUploadCard
              fileName={selectedFile?.name ?? null}
              loading={busy}
              onFileSelect={setSelectedFile}
              onPrepare={handlePrepare}
            />
            <CompileResultPanel
              ok={compileOk}
              error={compileError}
              commandCount={moveCount + strokeCount * 2}
              strokeCount={strokeCount}
              penSafe={penSafe}
            />
            <RobotControlPanel
              hasCommands={Boolean(commandsText)}
              busy={busy}
              simulationActive={Boolean(simJobId)}
              onDryRun={runDryRun}
              onSimulate={runSimulate}
              onLive={runLive}
              onLiveStop={runLiveStop}
              onSimStop={runSimStop}
            />
          </div>

          <div className="space-y-6 lg:col-span-8">
            <PlanPreviewPanel
              planName={planName}
              pointCount={pathPoints.length}
              strokeCount={strokeCount}
              points={pathPoints}
            />
            <CommandLogPanel
              commandsPreview={commandsText ? commandsPreview(commandsText) : ""}
              activityLog={activityLog}
              lastError={lastError}
              lastSuccess={lastSuccess}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
