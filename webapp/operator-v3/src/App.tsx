import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CadPreviewPanel } from "./components/CadPreviewPanel";
import { CommandStream } from "./components/CommandStream";
import { DemoWorkflowPanel } from "./components/DemoWorkflowPanel";
import { MissionShell } from "./components/MissionShell";
import { PipelineStepper, type PipelineStepId } from "./components/PipelineStepper";
import { RobotControlDeck } from "./components/RobotControlDeck";
import { SafetyNotice } from "./components/SafetyNotice";
import { TelemetryPanel } from "./components/TelemetryPanel";
import type { ActiveMode, MissionSection, StepStatus } from "./content/tr";
import { tr } from "./content/tr";
import {
  analyzeCommands,
  countStrokes,
  createSimulationJob,
  executeSerial,
  extractCommandsText,
  fetchHealth,
  formatUserError,
  importDxf,
  importPlanJson,
  isPenSafeCommands,
  isSupportedPlanFile,
  stopLiveSerial,
  stopSimulationJob,
} from "./services/api";
import { loadDemoPlan, type DemoPlanId } from "./services/demoPlans";
import type { AnalyzeResponse } from "./types/api";
import type { ActionFeedback } from "./lib/workflowState";
import {
  buildDryRunFeedback,
  buildLiveFeedback,
  buildSimFeedback,
  formatActivityLog,
  formatDryRunLog,
  formatLiveLog,
  formatSimLog,
  INITIAL_PIPELINE,
  isDryRunSuccess,
  newPlanActivityLog,
  pipelineAfterCompile,
  pipelineAfterFileSelect,
} from "./lib/workflowState";

const SECTION_IDS: Record<MissionSection, string> = {
  sistem: "section-sistem",
  plan: "section-plan",
  derleme: "section-derleme",
  simulasyon: "section-simulasyon",
  robot: "section-robot",
  loglar: "section-loglar",
};

function formatTime(d: Date) {
  return d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function App() {
  const [activeSection, setActiveSection] = useState<MissionSection>("sistem");
  const [backendOnline, setBackendOnline] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(formatTime(new Date()));
  const [activeMode, setActiveMode] = useState<ActiveMode>("idle");
  const [robotLabel, setRobotLabel] = useState<string>(tr.telemetry.unknown);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [planName, setPlanName] = useState<string | null>(null);
  const [commandsText, setCommandsText] = useState("");
  const [walls, setWalls] = useState<number[][]>([]);
  const [pathPoints, setPathPoints] = useState<number[][]>([]);
  const [preflight, setPreflight] = useState<AnalyzeResponse | null>(null);
  const [pipeline, setPipeline] = useState(INITIAL_PIPELINE);
  const [penSafeKnown, setPenSafeKnown] = useState(false);
  const [penSafe, setPenSafe] = useState(false);

  const [busy, setBusy] = useState(false);
  const [simJobId, setSimJobId] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [serialMode, setSerialMode] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);

  const sectionRefs = useRef<Partial<Record<MissionSection, HTMLElement | null>>>({});

  const strokeCount = useMemo(
    () => (commandsText ? countStrokes(commandsText) : 0),
    [commandsText],
  );

  const pushLog = useCallback((line: string) => {
    setActivityLog((prev) => [line, ...prev].slice(0, 40));
    setLastUpdate(formatTime(new Date()));
  }, []);

  const setStep = useCallback((id: PipelineStepId, status: StepStatus) => {
    setPipeline((prev) => ({ ...prev, [id]: status }));
  }, []);

  const resetPlanWorkflow = useCallback(
    (fileName: string) => {
      setCommandsText("");
      setWalls([]);
      setPathPoints([]);
      setPreflight(null);
      setPlanName(null);
      setPipeline(pipelineAfterFileSelect());
      setPenSafeKnown(false);
      setPenSafe(false);
      setSimJobId(null);
      setSerialMode(null);
      setActiveMode("idle");
      setRobotLabel(tr.telemetry.unknown);
      setActionFeedback(null);
      setActivityLog(newPlanActivityLog(fileName));
      setLastUpdate(formatTime(new Date()));
    },
    [],
  );

  const refreshHealth = useCallback(async () => {
    try {
      const h = await fetchHealth();
      setBackendOnline(Boolean(h.ok));
    } catch {
      setBackendOnline(false);
    }
    setLastUpdate(formatTime(new Date()));
  }, []);

  useEffect(() => {
    void refreshHealth();
    const id = window.setInterval(() => void refreshHealth(), 12000);
    return () => window.clearInterval(id);
  }, [refreshHealth]);

  const navigate = useCallback((section: MissionSection) => {
    setActiveSection(section);
    const el = sectionRefs.current[section];
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const scrollToLogs = useCallback(() => {
    navigate("loglar");
  }, [navigate]);

  function handleFileSelect(file: File) {
    if (!isSupportedPlanFile(file)) {
      pushLog(formatActivityLog("ERR", tr.errors.unsupportedFile));
      return;
    }
    resetPlanWorkflow(file.name);
    setSelectedFile(file);
  }

  async function compileFile(file: File) {
    if (!backendOnline) {
      pushLog(formatActivityLog("ERR", tr.errors.backendOffline));
      return;
    }
    if (!isSupportedPlanFile(file)) {
      pushLog(formatActivityLog("ERR", tr.errors.unsupportedFile));
      return;
    }

    setActionFeedback(null);
    setSimJobId(null);
    setSerialMode(null);
    setActiveMode("idle");
    setPipeline((prev) => ({
      ...prev,
      upload: "ready",
      analyze: "waiting",
      compile: "waiting",
      simulate: "waiting",
      send: "waiting",
    }));

    pushLog(formatActivityLog("INFO", `Plan yükleniyor: ${file.name}`));

    const ext = file.name.split(".").pop()?.toLowerCase();
    const res = ext === "json" ? await importPlanJson(file) : await importDxf(file);

    if (!res.ok) throw new Error(res.error ?? tr.errors.importFailed);

    const cmds = extractCommandsText(res);
    if (!cmds.trim()) throw new Error(tr.errors.noCommands);

    setCommandsText(cmds);
    setWalls(res.walls ?? []);
    setPathPoints(res.raw_path_points ?? []);
    setPlanName(file.name);

    const safe = isPenSafeCommands(cmds);
    setPenSafeKnown(true);
    setPenSafe(safe);

    const analysis = await analyzeCommands(cmds, res.walls);
    setPreflight(analysis);
    setPipeline(pipelineAfterCompile(safe));

    pushLog(
      safe
        ? formatActivityLog("OK", "Pen-safe compile tamamlandı")
        : formatActivityLog("ERR", "Derleme tamamlandı — pen-safe kontrol edin"),
    );
    navigate("loglar");
  }

  async function handleCompile() {
    if (!selectedFile) return;
    setBusy(true);
    try {
      await compileFile(selectedFile);
    } catch (e) {
      const msg = formatUserError(e);
      setPipeline((prev) => ({ ...prev, upload: "error" }));
      pushLog(formatActivityLog("ERR", msg));
    } finally {
      setBusy(false);
    }
  }

  async function handleDemoSelect(id: DemoPlanId) {
    if (!backendOnline) {
      pushLog(formatActivityLog("ERR", tr.errors.backendOffline));
      return;
    }
    setBusy(true);
    try {
      const file = await loadDemoPlan(id);
      resetPlanWorkflow(file.name);
      setSelectedFile(file);
      await compileFile(file);
    } catch (e) {
      setPipeline((prev) => ({ ...prev, upload: "error" }));
      pushLog(formatActivityLog("ERR", formatUserError(e)));
    } finally {
      setBusy(false);
    }
  }

  async function runDryRun() {
    if (!commandsText.trim()) {
      setActionFeedback(buildDryRunFeedback("error", undefined, tr.control.dryRunNoCommands));
      pushLog(formatActivityLog("ERR", tr.control.dryRunNoCommands));
      scrollToLogs();
      return;
    }
    if (!backendOnline) {
      setActionFeedback(buildDryRunFeedback("error", undefined, tr.errors.backendOffline));
      pushLog(formatActivityLog("ERR", tr.errors.backendOffline));
      scrollToLogs();
      return;
    }

    setBusy(true);
    setActiveMode("dryRun");
    setActionFeedback(buildDryRunFeedback("running"));
    pushLog(formatActivityLog("DRY", "Dry-run başlatıldı"));

    try {
      const res = await executeSerial(commandsText, {
        dryRun: true,
        walls,
        preflight: preflight ?? undefined,
      });

      if (isDryRunSuccess(res)) {
        setRobotLabel(res.status);
        setSerialMode("dry_run");
        setActionFeedback(buildDryRunFeedback("success", res));
        pushLog(formatDryRunLog(true, res.message));
      } else {
        const msg = res.message || res.error_detail || "Dry-run başarısız";
        setActionFeedback(buildDryRunFeedback("error", res, msg));
        pushLog(formatDryRunLog(false, msg));
      }
      scrollToLogs();
    } catch (e) {
      const msg = formatUserError(e);
      setActionFeedback(buildDryRunFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", msg));
      scrollToLogs();
    } finally {
      setBusy(false);
    }
  }

  async function runSimulate() {
    if (!commandsText.trim()) {
      setActionFeedback(buildSimFeedback("error", undefined, tr.control.dryRunNoCommands));
      pushLog(formatActivityLog("ERR", tr.control.dryRunNoCommands));
      scrollToLogs();
      return;
    }
    if (!backendOnline) {
      setActionFeedback(buildSimFeedback("error", undefined, tr.errors.backendOffline));
      pushLog(formatActivityLog("ERR", tr.errors.backendOffline));
      scrollToLogs();
      return;
    }

    setBusy(true);
    setActiveMode("simulation");
    setStep("simulate", "ready");
    setActionFeedback(buildSimFeedback("running"));
    pushLog(formatActivityLog("SIM", "Simülasyon işi oluşturuluyor"));

    try {
      const job = await createSimulationJob(commandsText, walls);
      setSimJobId(job.job_id);
      setStep("simulate", "success");
      setRobotLabel(`Sim: ${job.job_id.slice(0, 8)}`);
      setActionFeedback(buildSimFeedback("success", job.job_id));
      pushLog(formatSimLog(job.job_id));
      pushLog(formatActivityLog("SIM", "Canlı animasyon henüz bağlı değil."));
      scrollToLogs();
    } catch (e) {
      const msg = formatUserError(e);
      setStep("simulate", "error");
      setActionFeedback(buildSimFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", msg));
      scrollToLogs();
    } finally {
      setBusy(false);
    }
  }

  async function runLive() {
    if (!commandsText.trim()) {
      pushLog(formatActivityLog("ERR", tr.control.dryRunNoCommands));
      scrollToLogs();
      return;
    }
    if (!backendOnline) {
      pushLog(formatActivityLog("ERR", tr.errors.backendOffline));
      scrollToLogs();
      return;
    }

    setBusy(true);
    setActiveMode("live");
    setStep("send", "ready");
    setActionFeedback(buildLiveFeedback("running"));
    pushLog(formatActivityLog("INFO", "Canlı gönderim başlatıldı"));

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

      const liveOk = res.ok === true || res.status === "sent";
      setRobotLabel(res.status);
      setSerialMode(res.mode ?? "live");
      setStep("send", liveOk ? "success" : "error");
      setActionFeedback(
        liveOk ? buildLiveFeedback("success", res) : buildLiveFeedback("error", res, res.message),
      );
      pushLog(formatLiveLog(liveOk, res.message));
      scrollToLogs();
    } catch (e) {
      const msg = formatUserError(e);
      setStep("send", "error");
      setActionFeedback(buildLiveFeedback("error", undefined, msg));
      pushLog(formatLiveLog(false, msg));
      scrollToLogs();
    } finally {
      setBusy(false);
    }
  }

  async function runLiveStop() {
    setBusy(true);
    pushLog(formatActivityLog("INFO", "Canlı STOP isteği gönderildi"));
    try {
      const res = await stopLiveSerial();
      setRobotLabel(res.stopped ? "Durduruldu" : res.status);
      pushLog(formatActivityLog("OK", res.message));
      scrollToLogs();
    } catch (e) {
      pushLog(formatActivityLog("ERR", formatUserError(e)));
      scrollToLogs();
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
      setActiveMode("idle");
      setStep("simulate", "waiting");
      setActionFeedback(null);
      pushLog(formatActivityLog("OK", "Simülasyon durduruldu"));
      scrollToLogs();
    } catch (e) {
      pushLog(formatActivityLog("ERR", formatUserError(e)));
      scrollToLogs();
    } finally {
      setBusy(false);
    }
  }

  const bindSection = (id: MissionSection) => (el: HTMLElement | null) => {
    sectionRefs.current[id] = el;
  };

  return (
    <MissionShell
      activeSection={activeSection}
      onNavigate={navigate}
      backendOnline={backendOnline}
      robotLabel={robotLabel}
      activeMode={activeMode}
      lastUpdate={lastUpdate}
      onStop={runLiveStop}
      stopBusy={busy}
    >
      <div className="mx-auto max-w-[1600px] space-y-6">
        <SafetyNotice />

        <DemoWorkflowPanel
          pipeline={pipeline}
          hasCommands={Boolean(commandsText)}
          backendOnline={backendOnline}
          busy={busy}
          onDemoSelect={handleDemoSelect}
        />

        <section id={SECTION_IDS.sistem} ref={bindSection("sistem")} className="scroll-mt-4">
          <PipelineStepper statuses={pipeline} busy={busy} />
        </section>

        <div className="grid gap-6 xl:grid-cols-12">
          <div className="space-y-6 xl:col-span-8">
            <section id={SECTION_IDS.plan} ref={bindSection("plan")} className="scroll-mt-4">
              <CadPreviewPanel planName={planName} points={pathPoints} strokeCount={strokeCount} />
            </section>

            <section id={SECTION_IDS.derleme} ref={bindSection("derleme")} className="scroll-mt-4" />

            <section id={SECTION_IDS.robot} ref={bindSection("robot")} className="scroll-mt-4">
              <RobotControlDeck
                hasCommands={Boolean(commandsText)}
                busy={busy}
                simulationActive={Boolean(simJobId)}
                selectedFileName={selectedFile?.name ?? null}
                actionFeedback={actionFeedback}
                onFileSelect={handleFileSelect}
                onCompile={handleCompile}
                onDryRun={runDryRun}
                onSimulate={runSimulate}
                onLive={runLive}
                onLiveStop={runLiveStop}
                onSimStop={runSimStop}
              />
            </section>

            <section id={SECTION_IDS.simulasyon} ref={bindSection("simulasyon")} className="scroll-mt-4" />

            <section id={SECTION_IDS.loglar} ref={bindSection("loglar")} className="scroll-mt-4">
              <CommandStream commandsText={commandsText} activityLog={activityLog} />
            </section>
          </div>

          <div className="xl:col-span-4">
            <div className="sticky top-4">
              <TelemetryPanel
                backendOnline={backendOnline}
                penSafe={penSafe}
                penSafeKnown={penSafeKnown}
                serialMode={serialMode}
                lastRobotStatus={robotLabel}
              />
            </div>
          </div>
        </div>
      </div>
    </MissionShell>
  );
}
