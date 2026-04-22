import React, { useMemo, useState } from "react";
import StageFrame from "../../ui/StageFrame.jsx";
import { useCreateJobMutation, useExecuteSerialMutation, useStopJobMutation } from "../../core/data/hooks.js";
import { useExecutionLifecycle } from "../../core/lifecycle/executionLifecycle.js";
import { useWorkflow } from "../../core/workflow/WorkflowProvider.jsx";

export default function ExecutePage() {
  const { state, updateExecute } = useWorkflow();
  const [mode, setMode] = useState("simulate");
  const [stopStatus, setStopStatus] = useState("");
  const createJob = useCreateJobMutation();
  const stopJob = useStopJobMutation();
  const executeSerial = useExecuteSerialMutation();
  const hasCommands = Boolean(state.prepare.commandsText?.trim());
  const lifecycle = useExecutionLifecycle({
    onEvent: (event) => updateExecute({ lastEvent: event }),
    onStateChange: (next, err) => updateExecute({ runState: next, error: err || "" }),
  });

  const readinessLevel = useMemo(() => {
    if (!hasCommands) return "blocked";
    if (lifecycle.streamState === "running" || createJob.isPending || executeSerial.isPending) return "running";
    if (state.execute.error) return "error";
    if (lifecycle.streamState === "done") return "done";
    return "ready";
  }, [createJob.isPending, executeSerial.isPending, hasCommands, lifecycle.streamState, state.execute.error]);

  async function start() {
    setStopStatus("");
    const job = await createJob.mutateAsync(state.prepare.commandsText);
    const jobId = job?.job_id ?? job?.jobId ?? "";
    updateExecute({ jobId, runState: "running", error: "" });
    lifecycle.start(jobId);
  }

  async function stop() {
    if (!state.execute.jobId) {
      setStopStatus("Durdurulacak aktif job bulunmuyor.");
      return;
    }
    try {
      const res = await stopJob.mutateAsync(state.execute.jobId);
      lifecycle.stop();
      updateExecute({ runState: "blocked" });
      if (res?.stopped === true) {
        setStopStatus("Stop basarili: job durduruldu.");
      } else {
        setStopStatus("Job zaten bitmis olabilir; stream kapatildi.");
      }
    } catch (e) {
      if (e?.status === 404) {
        lifecycle.stop();
        updateExecute({ runState: "done" });
        setStopStatus("Job bulunamadi: buyuk olasilikla tamamlandi ve temizlendi.");
      } else {
        setStopStatus(`Gercek hata: ${String(e?.message ?? e)}`);
      }
    }
  }

  async function runSerial(dryRun) {
    const result = await executeSerial.mutateAsync({ commandsText: state.prepare.commandsText, dryRun });
    updateExecute({ serialResult: result, runState: dryRun ? "ready" : "done" });
  }

  return (
    <StageFrame
        title="Execute"
        lead="Calistirma lifecycle: start, stop, reconnect, retry, recover."
        status={readinessLevel}
        main={
          <>
            <section className="panel">
              <h2>Calistirma modu</h2>
              <div className="actions">
                <button type="button" className={`btn ${mode === "simulate" ? "btn--primary" : ""}`} onClick={() => setMode("simulate")}>Simulasyon</button>
                <button type="button" className={`btn ${mode === "robot" ? "btn--primary" : ""}`} onClick={() => setMode("robot")}>Robot</button>
              </div>
              <div className="actions">
                <button type="button" className="btn btn--primary" onClick={start} disabled={!hasCommands || createJob.isPending}>Start</button>
                <button type="button" className="btn btn--danger" onClick={stop} disabled={!state.execute.jobId || stopJob.isPending}>Stop</button>
                <button type="button" className="btn" onClick={lifecycle.reconnect} disabled={!state.execute.jobId}>Reconnect</button>
                <button type="button" className="btn" onClick={lifecycle.retry} disabled={!state.execute.jobId}>Retry</button>
                <button type="button" className="btn" onClick={lifecycle.recover} disabled={!state.execute.jobId}>Recover</button>
              </div>
              {mode === "robot" ? (
                <div className="actions">
                  <button type="button" className="btn" onClick={() => runSerial(true)} disabled={executeSerial.isPending || !hasCommands}>On kontrol</button>
                  <button type="button" className="btn btn--danger" onClick={() => runSerial(false)} disabled={executeSerial.isPending || !hasCommands}>Canli gonder</button>
                </div>
              ) : null}
              {stopStatus ? <div className="note">{stopStatus}</div> : null}
              {state.execute.error ? <div className="note note--err">{state.execute.error}</div> : null}
            </section>
            <section className="panel">
              <h2>Stream durum</h2>
              <div className="kv">
                <div><small>State</small><strong>{lifecycle.streamState}</strong></div>
                <div><small>Job</small><strong>{state.execute.jobId || "-"}</strong></div>
              </div>
              {state.execute.lastEvent ? <pre className="mono">{JSON.stringify(state.execute.lastEvent, null, 2)}</pre> : <div className="note">Event bekleniyor.</div>}
              {state.execute.serialResult ? <pre className="mono">{JSON.stringify(state.execute.serialResult, null, 2)}</pre> : null}
            </section>
          </>
        }
        side={
          <section className="panel">
            <h2>Karar</h2>
            <p>{hasCommands ? "Calistirma icin komut hazir." : "Prepare/Plan adimini tamamlayin."}</p>
            <div className="kv">
              <div><small>Mode</small><strong>{mode}</strong></div>
              <div><small>Run</small><strong>{state.execute.runState}</strong></div>
            </div>
          </section>
        }
      />
  );
}
