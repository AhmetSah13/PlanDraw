import { describe, expect, it } from "vitest";
import { normalizeStreamEvent } from "../lifecycle/executionLifecycle.js";
import { deriveWorkflowMeta, workflowInitialState, workflowReducer } from "./workflowMachine.js";

describe("Prepare->Align->Plan->Execute->Monitor smoke", () => {
  it("adim akisini guard kurallariyla ilerletir", () => {
    let state = workflowInitialState;

    let meta = deriveWorkflowMeta(state);
    expect(meta.nextStep).toBe("/prepare");
    expect(meta.readiness.prepare).toBe("blocked");

    state = workflowReducer(state, {
      type: "prepare/update",
      payload: { commandsText: "MOVE 0 0\nPEN DOWN\nMOVE 10 10", walls: [[0, 0, 10, 0]], rawPath: [[0, 0], [10, 10]] },
    });
    meta = deriveWorkflowMeta(state);
    expect(meta.nextStep).toBe("/align");
    expect(meta.readiness.prepare).toBe("done");

    state = workflowReducer(state, {
      type: "align/update",
      payload: { alignment: { gate: "allowed", score: 0.99 }, controlPoints: [{ cad: [0, 0], site: [1, 1] }] },
    });
    meta = deriveWorkflowMeta(state);
    expect(meta.nextStep).toBe("/plan");
    expect(meta.readiness.align).toBe("done");

    state = workflowReducer(state, { type: "plan/update", payload: { planReady: true } });
    meta = deriveWorkflowMeta(state);
    expect(meta.nextStep).toBe("/execute");
    expect(meta.readiness.plan).toBe("done");

    state = workflowReducer(state, { type: "execute/update", payload: { jobId: "job-1", runState: "running" } });
    meta = deriveWorkflowMeta(state);
    expect(meta.nextStep).toBe("/monitor");
    expect(meta.readiness.execute).toBe("running");
  });

  it("stream event normalizasyonu stabil kalir", () => {
    const raw = { phase: "tick", message: "ilerliyor", progress: 42 };
    const normalized = normalizeStreamEvent(raw);
    expect(normalized.phase).toBe("tick");
    expect(normalized.message).toBe("ilerliyor");
    expect(normalized.progress).toBe(42);
    expect(typeof normalized.at).toBe("number");
  });
});
