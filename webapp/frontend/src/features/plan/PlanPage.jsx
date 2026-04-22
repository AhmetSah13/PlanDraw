import React, { useMemo, useState } from "react";
import StageFrame from "../../ui/StageFrame.jsx";
import { useAnalyzeMutation, useOptimizeMutation } from "../../core/data/hooks.js";
import { useWorkflow } from "../../core/workflow/WorkflowProvider.jsx";

export default function PlanPage() {
  const { state, updatePrepare, updatePlan } = useWorkflow();
  const optimize = useOptimizeMutation();
  const analyze = useAnalyzeMutation();
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const hasCommands = Boolean(state.prepare.commandsText?.trim());

  const readinessLevel = useMemo(() => {
    if (!hasCommands) return "blocked";
    if (optimize.isPending || analyze.isPending) return "running";
    if (error) return "error";
    if (state.plan.planReady) return "done";
    return "ready";
  }, [analyze.isPending, error, hasCommands, optimize.isPending, state.plan.planReady]);

  async function runPlanCheck() {
    setError("");
    setInfo("");
    try {
      const res = await optimize.mutateAsync(state.prepare.commandsText);
      updatePrepare({
        commandsText: res.commands_text ?? state.prepare.commandsText,
        rawPath: res.raw_path_points ?? state.prepare.rawPath,
      });
      updatePlan({ planReady: !res?.blocked });
      setInfo(res?.blocked ? "Plan kontrolunde engel bulundu." : "Plan kontrolu temiz.");
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  async function runValidate() {
    setError("");
    setInfo("");
    try {
      const res = await analyze.mutateAsync(state.prepare.commandsText);
      if (res?.blocked) {
        updatePlan({ planReady: false });
        setInfo("Plan dogrulama engelli.");
      } else {
        updatePlan({ planReady: true });
        setInfo("Plan execute icin hazir.");
      }
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  return (
    <StageFrame
        title="Plan"
        lead="Bu adimda plani analiz edip execute oncesi kontrol edersiniz."
        status={readinessLevel}
        main={
          <>
            <section className="panel">
              <h2>Plan kontrolu</h2>
              <p>Bu adim optimize degil; analiz ve dogrulama adimidir.</p>
              <div className="actions">
                <button type="button" className="btn btn--primary" onClick={runPlanCheck} disabled={!hasCommands || optimize.isPending}>
                  {optimize.isPending ? "Analiz..." : "Plani kontrol et"}
                </button>
                <button type="button" className="btn" onClick={runValidate} disabled={!hasCommands || analyze.isPending}>
                  {analyze.isPending ? "Dogrulama..." : "Plani dogrula"}
                </button>
              </div>
              {error ? <div className="note note--err">{error}</div> : null}
              {info ? <div className="note note--ok">{info}</div> : null}
            </section>
            <section className="panel">
              <h2>Komut ozet</h2>
              <pre className="mono">{state.prepare.commandsText || "(komut yok)"}</pre>
            </section>
          </>
        }
        side={
          <section className="panel">
            <h2>Karar</h2>
            <p>{state.plan.planReady ? "Plan kontrolu gecerli. Execute adimina gecebilirsiniz." : "Plan kontrolu henuz tamam degil."}</p>
            <div className="kv">
              <div><small>Kontrol durumu</small><strong>{state.plan.planReady ? "hazir" : "bekliyor"}</strong></div>
              <div><small>Path</small><strong>{state.prepare.rawPath?.length ?? 0}</strong></div>
            </div>
          </section>
        }
      />
  );
}
