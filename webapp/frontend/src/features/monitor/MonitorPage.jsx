import React, { useMemo } from "react";
import StageFrame from "../../ui/StageFrame.jsx";
import { useWorkflow } from "../../core/workflow/WorkflowProvider.jsx";

export default function MonitorPage() {
  const { state, nextStep } = useWorkflow();

  const readinessLevel = useMemo(() => {
    if (state.execute.runState === "running") return "running";
    if (state.execute.runState === "done") return "done";
    if (state.execute.error) return "error";
    if (state.execute.lastEvent) return "ready";
    return "blocked";
  }, [state.execute.error, state.execute.lastEvent, state.execute.runState]);

  return (
    <StageFrame
        title="Monitor"
        lead="Calistirma sonucu ve event akisini izleyin."
        status={readinessLevel}
        main={
          <>
            <section className="panel">
              <h2>Canli durum</h2>
              <div className="kv">
                <div>
                  <small>Job</small>
                  <strong>{state.execute.jobId || "-"}</strong>
                </div>
                <div>
                  <small>Run state</small>
                  <strong>{state.execute.runState}</strong>
                </div>
              </div>
              {state.execute.lastEvent ? <pre className="mono">{JSON.stringify(state.execute.lastEvent, null, 2)}</pre> : <div className="note">Henuz event yok.</div>}
            </section>
            <section className="panel">
              <h2>Serial ozet</h2>
              {state.execute.serialResult ? (
                <pre className="mono">{JSON.stringify(state.execute.serialResult, null, 2)}</pre>
              ) : (
                <div className="note">Serial sonuc yok.</div>
              )}
              {state.execute.error ? <div className="note note--err">{state.execute.error}</div> : null}
            </section>
          </>
        }
        side={
          <section className="panel">
            <h2>Sonraki adim</h2>
            <p>Workflow yonlendirmesi aktif.</p>
            <div className="kv">
              <div>
                <small>Next</small>
                <strong>{nextStep}</strong>
              </div>
              <div>
                <small>Komut</small>
                <strong>{state.prepare.commandsText ? "var" : "yok"}</strong>
              </div>
            </div>
          </section>
        }
      />
  );
}
