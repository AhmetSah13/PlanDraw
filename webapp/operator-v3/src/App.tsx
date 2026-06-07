import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CadPreviewPanel } from "./components/CadPreviewPanel";
import { CommandStream } from "./components/CommandStream";
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
import type { AnalyzeResponse } from "./types/api";

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

const initialPipeline: Record<PipelineStepId, StepStatus> = {
  upload: "waiting",
  analyze: "waiting",
  compile: "waiting",
  simulate: "waiting",
  send: "waiting",
};

export default function App() {
  const [activeSection, setActiveSection] = useState<MissionSection>("sistem");
  const [backendOnline, setBackendOnline] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(formatTime(new Date()));
  const [activeMode, setActiveMode] = useState<ActiveMode>("idle");
  const [robotLabel, setRobotLabel] = useState("Bilinmiyor");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [planName, setPlanName] = useState<string | null>(null);
  const [commandsText, setCommandsText] = useState("");
  const [walls, setWalls] = useState<number[][]>([]);
  const [pathPoints, setPathPoints] = useState<number[][]>([]);
  const [preflight, setPreflight] = useState<AnalyzeResponse | null>(null);
  const [pipeline, setPipeline] = useState(initialPipeline);
  const [penSafeKnown, setPenSafeKnown] = useState(false);
  const [penSafe, setPenSafe] = useState(false);

  const [busy, setBusy] = useState(false);
  const [simJobId, setSimJobId] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [serialMode, setSerialMode] = useState<string | null>(null);

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

  function handleFileSelect(file: File) {
    if (!isSupportedPlanFile(file)) {
      pushLog(tr.errors.unsupportedFile);
      return;
    }
    setSelectedFile(file);
  }

  async function handleCompile() {
    if (!selectedFile) return;
    if (!backendOnline) {
      pushLog(tr.errors.backendOffline);
      return;
    }
    if (!isSupportedPlanFile(selectedFile)) {
      pushLog(tr.errors.unsupportedFile);
      return;
    }

    setBusy(true);
    setStep("upload", "ready");
    pushLog(`Plan yükleniyor: ${selectedFile.name}`);

    try {
      const ext = selectedFile.name.split(".").pop()?.toLowerCase();
      const res =
        ext === "json" ? await importPlanJson(selectedFile) : await importDxf(selectedFile);

      if (!res.ok) throw new Error(res.error ?? tr.errors.importFailed);

      setStep("upload", "success");
      setStep("analyze", "ready");

      const cmds = extractCommandsText(res);
      if (!cmds.trim()) throw new Error(tr.errors.noCommands);

      setCommandsText(cmds);
      setWalls(res.walls ?? []);
      setPathPoints(res.raw_path_points ?? []);
      setPlanName(selectedFile.name);

      const safe = isPenSafeCommands(cmds);
      setPenSafeKnown(true);
      setPenSafe(safe);

      const analysis = await analyzeCommands(cmds, res.walls);
      setPreflight(analysis);
      setStep("analyze", "success");
      setStep("compile", safe ? "success" : "error");

      pushLog(safe ? "Pen-safe derleme doğrulandı" : "Derleme tamamlandı — pen-safe kontrol edin");
      navigate("derleme");
    } catch (e) {
      const msg = formatUserError(e);
      setStep("upload", "error");
      pushLog(`Hata: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function runDryRun() {
    if (!commandsText) return;
    setBusy(true);
    setActiveMode("dryRun");
    setStep("send", "ready");
    pushLog("Dry-run başlatıldı");
    try {
      const res = await executeSerial(commandsText, {
        dryRun: true,
        walls,
        preflight: preflight ?? undefined,
      });
      setRobotLabel(res.status);
      setSerialMode("dry_run");
      setStep("send", "success");
      pushLog(res.message);
    } catch (e) {
      setStep("send", "error");
      pushLog(formatUserError(e));
    } finally {
      setBusy(false);
    }
  }

  async function runSimulate() {
    if (!commandsText) return;
    setBusy(true);
    setActiveMode("simulation");
    setStep("simulate", "ready");
    pushLog("Simülasyon job oluşturuluyor");
    try {
      const job = await createSimulationJob(commandsText, walls);
      setSimJobId(job.job_id);
      setStep("simulate", "success");
      setRobotLabel(`Sim: ${job.job_id.slice(0, 8)}`);
      pushLog(`Job: ${job.job_id}`);
      navigate("simulasyon");
    } catch (e) {
      setStep("simulate", "error");
      pushLog(formatUserError(e));
    } finally {
      setBusy(false);
    }
  }

  async function runLive() {
    if (!commandsText) return;
    setBusy(true);
    setActiveMode("live");
    setStep("send", "ready");
    pushLog("Canlı gönderim");
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
      setRobotLabel(res.status);
      setSerialMode(res.mode ?? "live");
      setStep("send", res.status === "sent" || res.ok ? "success" : "ready");
      pushLog(res.message);
      navigate("robot");
    } catch (e) {
      setStep("send", "error");
      pushLog(formatUserError(e));
    } finally {
      setBusy(false);
    }
  }

  async function runLiveStop() {
    setBusy(true);
    pushLog("Canlı STOP");
    try {
      const res = await stopLiveSerial();
      setRobotLabel(res.stopped ? "Durduruldu" : res.status);
      pushLog(res.message);
    } catch (e) {
      pushLog(formatUserError(e));
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
      pushLog("Simülasyon durduruldu");
    } catch (e) {
      pushLog(formatUserError(e));
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
