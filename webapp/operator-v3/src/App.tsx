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
import { getDemoPlanMeta, loadDemoPlan, type DemoPlanId } from "./services/demoPlans";
import type { AnalyzeResponse } from "./types/api";
import {
  buildSimulationPreview,
  buildSimulationSegments,
  createIdlePlayback,
  startPlayback,
  type SimPlayback,
} from "./lib/commandSimulation";
import type { ActionFeedback } from "./lib/workflowState";
import {
  buildDryRunFeedback,
  buildLiveFeedback,
  buildPlanResetPatch,
  buildSimFeedback,
  formatActivityLog,
  formatDryRunLog,
  formatLiveLog,
  formatSimLog,
  INITIAL_PIPELINE,
  isDryRunSuccess,
  isPlanSessionCurrent,
  nextPlanSessionId,
  pipelineAfterCompile,
  pipelineAfterDerivedReset,
} from "./lib/workflowState";
import {
  buildWorkflowAvailability,
  getPostCompileNavigation,
  resetDerivedPipelineForAction,
  SECTION_IDS,
  type CompileSource,
} from "./lib/operatorFlow";

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
  const [simPlayback, setSimPlayback] = useState<SimPlayback>(createIdlePlayback);
  const [dryRunPassed, setDryRunPassed] = useState(false);

  const sectionRefs = useRef<Partial<Record<MissionSection, HTMLElement | null>>>({});
  const simRunCounter = useRef(0);
  const planSessionRef = useRef(0);
  const playbackSessionRef = useRef(0);

  const strokeCount = useMemo(
    () => (commandsText ? countStrokes(commandsText) : 0),
    [commandsText],
  );

  const workflowAvailability = useMemo(
    () =>
      buildWorkflowAvailability({
        backendOnline,
        busy,
        hasSelectedFile: Boolean(selectedFile),
        hasCommands: Boolean(commandsText.trim()),
        compileStatus: pipeline.compile,
        simulationStatus: pipeline.simulate,
        dryRunPassed,
        preflight,
        penSafeKnown,
        penSafe,
      }),
    [
      backendOnline,
      busy,
      selectedFile,
      commandsText,
      pipeline.compile,
      pipeline.simulate,
      dryRunPassed,
      preflight,
      penSafeKnown,
      penSafe,
    ],
  );

  const pushLog = useCallback((line: string) => {
    setActivityLog((prev) => [line, ...prev].slice(0, 40));
    setLastUpdate(formatTime(new Date()));
  }, []);

  const setStep = useCallback((id: PipelineStepId, status: StepStatus) => {
    setPipeline((prev) => ({ ...prev, [id]: status }));
  }, []);

  const resetPlanWorkflow = useCallback((fileName: string) => {
    planSessionRef.current = nextPlanSessionId(planSessionRef.current);
    playbackSessionRef.current = 0;
    simRunCounter.current = 0;
    setBusy(false);

    const patch = buildPlanResetPatch(fileName);
    setCommandsText(patch.commandsText);
    setWalls(patch.walls);
    setPathPoints(patch.pathPoints);
    setPreflight(patch.preflight);
    setPlanName(patch.planName);
    setPipeline(patch.pipeline);
    setPenSafeKnown(patch.penSafeKnown);
    setPenSafe(patch.penSafe);
    setSimJobId(patch.simJobId);
    setSerialMode(patch.serialMode);
    setActiveMode(patch.activeMode);
    setRobotLabel(tr.telemetry.unknown);
    setActionFeedback(patch.actionFeedback);
    setSimPlayback(createIdlePlayback());
    setDryRunPassed(false);
    setActivityLog(patch.activityLog);
    setLastUpdate(formatTime(new Date()));
  }, []);

  const handlePlaybackUpdate = useCallback((next: SimPlayback) => {
    if (!isPlanSessionCurrent(playbackSessionRef.current, planSessionRef.current)) return;
    setSimPlayback(next);
  }, []);

  const handleSimulationComplete = useCallback(() => {
    if (!isPlanSessionCurrent(playbackSessionRef.current, planSessionRef.current)) return;
    pushLog(formatActivityLog("OK", tr.preview.simCompleted));
  }, [pushLog]);

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

  async function compileFile(file: File, source: CompileSource) {
    const session = planSessionRef.current;

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
    setSimPlayback(createIdlePlayback());
    playbackSessionRef.current = 0;
    setSerialMode(null);
    setActiveMode("idle");
    setRobotLabel(tr.telemetry.unknown);
    setPipeline(pipelineAfterDerivedReset());
    setDryRunPassed(false);

    pushLog(formatActivityLog("INFO", `Plan yükleniyor: ${file.name}`));

    const ext = file.name.split(".").pop()?.toLowerCase();
    const res = ext === "json" ? await importPlanJson(file) : await importDxf(file);
    if (!isPlanSessionCurrent(session, planSessionRef.current)) return;

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
    if (!isPlanSessionCurrent(session, planSessionRef.current)) return;

    setPreflight(analysis);
    setPipeline(pipelineAfterCompile(safe));

    pushLog(
      safe
        ? formatActivityLog("OK", "Pen-safe compile tamamlandı")
        : formatActivityLog("ERR", "Derleme tamamlandı — pen-safe kontrol edin"),
    );
    const target = getPostCompileNavigation(source);
    if (target) navigate(target);
  }

  async function handleCompile() {
    if (!selectedFile) return;
    const session = planSessionRef.current;
    setBusy(true);
    try {
      await compileFile(selectedFile, "manual");
    } catch (e) {
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      const msg = formatUserError(e);
      setPipeline((prev) => ({ ...prev, upload: "error" }));
      pushLog(formatActivityLog("ERR", msg));
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
    }
  }

  async function handleDemoSelect(id: DemoPlanId) {
    if (!backendOnline) {
      pushLog(formatActivityLog("ERR", tr.errors.backendOffline));
      return;
    }
    setBusy(true);
    let session = planSessionRef.current;
    try {
      const meta = getDemoPlanMeta(id);
      resetPlanWorkflow(meta.file);
      setSelectedFile(null);
      session = planSessionRef.current;
      setBusy(true);
      const file = await loadDemoPlan(id);
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      setSelectedFile(file);
      await compileFile(file, "demo");
    } catch (e) {
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      setPipeline((prev) => ({ ...prev, upload: "error" }));
      pushLog(formatActivityLog("ERR", formatUserError(e)));
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
    }
  }

  async function runDryRun() {
    if (!workflowAvailability.canDryRun) {
      const msg = workflowAvailability.dryRunReason ?? tr.control.dryRunNoCommands;
      setActionFeedback(buildDryRunFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", msg));
      navigate("derleme");
      return;
    }
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

    const session = planSessionRef.current;
    setBusy(true);
    setActiveMode("dryRun");
    setActionFeedback(buildDryRunFeedback("running"));
    setDryRunPassed(false);
    setPipeline((prev) => resetDerivedPipelineForAction(prev, "dryRun"));
    pushLog(formatActivityLog("DRY", "Dry-run başlatıldı"));

    try {
      const res = await executeSerial(commandsText, {
        dryRun: true,
        walls,
        preflight: preflight ?? undefined,
      });
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;

      if (isDryRunSuccess(res)) {
        setRobotLabel(res.status);
        setSerialMode("dry_run");
        setActionFeedback(buildDryRunFeedback("success", res));
        setDryRunPassed(true);
        pushLog(formatDryRunLog(true, res.message));
      } else {
        const msg = res.message || res.error_detail || "Dry-run başarısız";
        setActionFeedback(buildDryRunFeedback("error", res, msg));
        setDryRunPassed(false);
        pushLog(formatActivityLog("ERR", `Dry-run başarısız: ${msg}`));
      }
      scrollToLogs();
    } catch (e) {
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      const msg = formatUserError(e);
      setActionFeedback(buildDryRunFeedback("error", undefined, msg));
      setDryRunPassed(false);
      pushLog(formatActivityLog("ERR", `Dry-run başarısız: ${msg}`));
      scrollToLogs();
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
    }
  }

  async function runSimulate() {
    if (!workflowAvailability.canSimulate) {
      const msg = workflowAvailability.simulateReason ?? tr.control.dryRunNoCommands;
      setActionFeedback(buildSimFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", msg));
      navigate("robot");
      return;
    }
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

    const session = planSessionRef.current;
    setBusy(true);
    setActiveMode("simulation");
    setStep("simulate", "ready");
    setPipeline((prev) => resetDerivedPipelineForAction(prev, "simulate"));
    setActionFeedback(buildSimFeedback("running"));
    pushLog(formatActivityLog("SIM", "Simülasyon işi oluşturuluyor"));

    try {
      const job = await createSimulationJob(commandsText, walls);
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;

      setSimJobId(job.job_id);
      setStep("simulate", "success");
      setRobotLabel(`Sim: ${job.job_id.slice(0, 8)}`);
      setActionFeedback(buildSimFeedback("success", job.job_id));
      pushLog(formatSimLog(job.job_id));
      pushLog(formatActivityLog("OK", tr.control.simJobCreated));
      simRunCounter.current += 1;
      playbackSessionRef.current = planSessionRef.current;
      const segs = buildSimulationSegments(commandsText, pathPoints);
      setSimPlayback(startPlayback(simRunCounter.current, segs));
      navigate("simulasyon");
    } catch (e) {
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      const msg = formatUserError(e);
      setStep("simulate", "error");
      setActionFeedback(buildSimFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", `Simülasyon başlatılamadı: ${msg}`));
      scrollToLogs();
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
    }
  }

  async function runSimulatePreview() {
    if (!workflowAvailability.canSimulate) {
      const msg = workflowAvailability.simulateReason ?? tr.control.dryRunNoCommands;
      setActionFeedback(buildSimFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", msg));
      navigate("robot");
      return;
    }
    if (!commandsText.trim()) {
      const msg = "Simülasyon için önce planı derleyin.";
      setActionFeedback(buildSimFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", msg));
      scrollToLogs();
      return;
    }

    const session = planSessionRef.current;
    setBusy(true);
    setActiveMode("simulation");
    setStep("simulate", "ready");
    setPipeline((prev) => resetDerivedPipelineForAction(prev, "simulate"));
    setActionFeedback(buildSimFeedback("running"));
    pushLog(formatActivityLog("SIM", "Simülasyon önizlemesi hazırlanıyor"));

    try {
      const preview = buildSimulationPreview(commandsText, pathPoints);
      if (!preview.segments.length) {
        const msg = preview.error ?? "Simülasyon için çizilebilir segment bulunamadı.";
        setStep("simulate", "error");
        setActionFeedback(buildSimFeedback("error", undefined, msg));
        pushLog(formatActivityLog("ERR", msg));
        navigate("robot");
        return;
      }
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;

      let jobId: string | null = null;
      if (backendOnline) {
        try {
          const job = await createSimulationJob(commandsText, walls);
          if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
          jobId = job.job_id;
          pushLog(formatSimLog(job.job_id));
          pushLog(formatActivityLog("OK", tr.control.simJobCreated));
        } catch (e) {
          if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
          pushLog(
            formatActivityLog(
              "ERR",
              `Backend simülasyon işi oluşturulamadı; yerel önizleme başlatıldı. ${formatUserError(e)}`,
            ),
          );
        }
      } else {
        pushLog(formatActivityLog("ERR", "Backend bağlantısı yok; yerel simülasyon önizlemesi başlatıldı."));
      }

      setSimJobId(jobId);
      setStep("simulate", "success");
      setRobotLabel(jobId ? `Sim: ${jobId.slice(0, 8)}` : "Yerel önizleme");
      setActionFeedback({
        kind: "simulate",
        phase: "success",
        title: "Simülasyon önizlemesi başlatıldı",
        message: jobId
          ? `Backend simülasyon işi oluşturuldu: job_id=${jobId}`
          : "Backend simülasyon işi olmadan yerel önizleme başlatıldı.",
        detail:
          preview.source === "commands"
            ? "Görsel önizleme komutlardan oluşturuldu; gerçek motor/zemin davranışını temsil etmez."
            : "Görsel önizleme path verisinden oluşturuldu; gerçek motor/zemin davranışını temsil etmez.",
      });
      for (const warning of preview.warnings.slice(0, 3)) {
        pushLog(formatActivityLog("INFO", `Simülasyon uyarısı satır ${warning.line}: ${warning.message}`));
      }
      simRunCounter.current += 1;
      playbackSessionRef.current = planSessionRef.current;
      setSimPlayback(startPlayback(simRunCounter.current, preview.segments));
      navigate("simulasyon");
    } catch (e) {
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      const msg = formatUserError(e);
      setStep("simulate", "error");
      setActionFeedback(buildSimFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", `Simülasyon başlatılamadı: ${msg}`));
      scrollToLogs();
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
    }
  }

  async function runLive() {
    if (!workflowAvailability.canLive) {
      const msg = workflowAvailability.liveReason ?? tr.control.dryRunNoCommands;
      setActionFeedback(buildLiveFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", msg));
      navigate("robot");
      return;
    }
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

    const session = planSessionRef.current;
    setBusy(true);
    setActiveMode("live");
    setStep("send", "ready");
    setActionFeedback(buildLiveFeedback("running"));
    pushLog(formatActivityLog("INFO", "Canlı gönderim başlatıldı"));

    try {
      const pf = await analyzeCommands(commandsText, walls, "error");
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      setPreflight(pf);
      if (pf.blocked) {
        setStep("send", "error");
        const msg = "Final analiz engelli döndü; canlı gönderim iptal edildi.";
        setActionFeedback(buildLiveFeedback("error", undefined, msg));
        pushLog(formatActivityLog("ERR", msg));
        navigate("robot");
        return;
      }
      const res = await executeSerial(commandsText, {
        dryRun: false,
        walls,
        preflight: pf,
      });
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;

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
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      const msg = formatUserError(e);
      setStep("send", "error");
      setActionFeedback(buildLiveFeedback("error", undefined, msg));
      pushLog(formatActivityLog("ERR", `Canlı gönderim başarısız: ${msg}`));
      scrollToLogs();
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
    }
  }

  async function runLiveStop() {
    const session = planSessionRef.current;
    setBusy(true);
    pushLog(formatActivityLog("INFO", "Canlı STOP isteği gönderildi"));
    try {
      const res = await stopLiveSerial();
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      setRobotLabel(res.stopped ? "Durduruldu" : res.status);
      pushLog(formatActivityLog("OK", res.message));
      scrollToLogs();
    } catch (e) {
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      pushLog(formatActivityLog("ERR", formatUserError(e)));
      scrollToLogs();
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
    }
  }

  async function runSimStop() {
    if (!simJobId) return;
    const session = planSessionRef.current;
    setBusy(true);
    try {
      await stopSimulationJob(simJobId);
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      setSimJobId(null);
      setSimPlayback(createIdlePlayback());
      playbackSessionRef.current = 0;
      setActiveMode("idle");
      setStep("simulate", "waiting");
      setActionFeedback(null);
      setRobotLabel(tr.telemetry.unknown);
      pushLog(formatActivityLog("OK", "Simülasyon durduruldu"));
      scrollToLogs();
    } catch (e) {
      if (!isPlanSessionCurrent(session, planSessionRef.current)) return;
      pushLog(formatActivityLog("ERR", formatUserError(e)));
      scrollToLogs();
    } finally {
      if (isPlanSessionCurrent(session, planSessionRef.current)) {
        setBusy(false);
      }
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
        <section id={SECTION_IDS.sistem} ref={bindSection("sistem")} className="scroll-mt-4 space-y-6">
          <SafetyNotice />
          <PipelineStepper statuses={pipeline} busy={busy} />
        </section>

        <section id={SECTION_IDS.plan} ref={bindSection("plan")} className="scroll-mt-4">
          <DemoWorkflowPanel
            pipeline={pipeline}
            hasCommands={Boolean(commandsText)}
            backendOnline={backendOnline}
            busy={busy}
            onDemoSelect={handleDemoSelect}
          />
        </section>

        <div className="grid gap-6 xl:grid-cols-12">
          <div className="space-y-6 xl:col-span-8">
            <section id={SECTION_IDS.simulasyon} ref={bindSection("simulasyon")} className="scroll-mt-4">
              <CadPreviewPanel
                planName={planName}
                points={pathPoints}
                strokeCount={strokeCount}
                commandsText={commandsText}
                simPlayback={simPlayback}
                simJobId={simJobId}
                onPlaybackUpdate={handlePlaybackUpdate}
                onSimulationComplete={handleSimulationComplete}
              />
            </section>

            <section className="scroll-mt-4">
              <RobotControlDeck
                hasCommands={Boolean(commandsText)}
                busy={busy}
                simulationActive={Boolean(simJobId)}
                selectedFileName={selectedFile?.name ?? null}
                actionFeedback={actionFeedback}
                canCompile={workflowAvailability.canCompile}
                canDryRun={workflowAvailability.canDryRun}
                canSimulate={workflowAvailability.canSimulate}
                canLive={workflowAvailability.canLive}
                compileReason={workflowAvailability.compileReason}
                dryRunReason={workflowAvailability.dryRunReason}
                simulateReason={workflowAvailability.simulateReason}
                liveReason={workflowAvailability.liveReason}
                compileAnchorId={SECTION_IDS.derleme}
                robotAnchorId={SECTION_IDS.robot}
                compileAnchorRef={bindSection("derleme")}
                robotAnchorRef={bindSection("robot")}
                onFileSelect={handleFileSelect}
                onCompile={handleCompile}
                onDryRun={runDryRun}
                onSimulate={runSimulatePreview}
                onLive={runLive}
                onLiveStop={runLiveStop}
                onSimStop={runSimStop}
              />
            </section>

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
