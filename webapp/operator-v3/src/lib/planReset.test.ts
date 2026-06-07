import { describe, expect, it } from "vitest";
import {
  buildPlanResetPatch,
  isPlanSessionCurrent,
  newPlanActivityLog,
  nextPlanSessionId,
  pipelineAfterDerivedReset,
  pipelineAfterFileSelect,
} from "./workflowState";

describe("plan reset", () => {
  it("yeni dosya seçilince dry-run/sim/live türev state temizlenir", () => {
    const patch = buildPlanResetPatch("iki_kopuk.dxf");
    expect(patch.commandsText).toBe("");
    expect(patch.actionFeedback).toBeNull();
    expect(patch.simJobId).toBeNull();
    expect(patch.serialMode).toBeNull();
    expect(patch.preflight).toBeNull();
    expect(patch.penSafeKnown).toBe(false);
    expect(patch.pipeline.simulate).toBe("waiting");
    expect(patch.pipeline.send).toBe("waiting");
    expect(patch.pipeline.analyze).toBe("waiting");
    expect(patch.pipeline.compile).toBe("waiting");
  });

  it("yeni dosya seçilince activityLog yalnızca INFO satırı içerir", () => {
    const patch = buildPlanResetPatch("demo_square_room.dxf");
    expect(patch.activityLog).toEqual(newPlanActivityLog("demo_square_room.dxf"));
    expect(patch.activityLog).toHaveLength(1);
  });

  it("pipeline upload hazır diğer adımlar bekliyor", () => {
    expect(buildPlanResetPatch("plan.dxf").pipeline).toEqual(pipelineAfterFileSelect());
  });

  it("pipelineAfterDerivedReset tüm türev adımları bekliyor yapar", () => {
    const next = pipelineAfterDerivedReset();
    expect(next.upload).toBe("ready");
    expect(next.simulate).toBe("waiting");
    expect(next.send).toBe("waiting");
    expect(next.analyze).toBe("waiting");
    expect(next.compile).toBe("waiting");
  });

  it("demo plan değişiminde session id artar", () => {
    expect(nextPlanSessionId(3)).toBe(4);
  });

  it("eski async sonucu yeni session ile uygulanamaz", () => {
    expect(isPlanSessionCurrent(1, 2)).toBe(false);
    expect(isPlanSessionCurrent(2, 2)).toBe(true);
  });
});
