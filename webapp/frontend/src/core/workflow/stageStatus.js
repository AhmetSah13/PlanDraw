export const STAGE = {
  BLOCKED: "blocked",
  READY: "ready",
  RUNNING: "running",
  DONE: "done",
  ERROR: "error",
};

export function nextStepFromSnapshot(snapshot) {
  if (!snapshot.prepare.commandsText) return "/prepare";
  if (!snapshot.align.alignment) return "/align";
  if (!snapshot.plan.planReady) return "/plan";
  if (!snapshot.execute.jobId) return "/execute";
  return "/monitor";
}

export function readinessFromSnapshot(snapshot) {
  return {
    prepare: snapshot.prepare.commandsText ? STAGE.DONE : STAGE.BLOCKED,
    align: snapshot.align.alignment ? STAGE.DONE : STAGE.BLOCKED,
    plan: snapshot.plan.planReady ? STAGE.DONE : STAGE.BLOCKED,
    execute: snapshot.execute.runState ?? STAGE.BLOCKED,
    monitor: snapshot.execute.lastEvent ? STAGE.READY : STAGE.BLOCKED,
  };
}
