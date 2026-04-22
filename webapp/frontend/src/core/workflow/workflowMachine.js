import { nextStepFromSnapshot, readinessFromSnapshot, STAGE } from "./stageStatus.js";

export const WORKFLOW_STORAGE_KEY = "operation_workflow_v2";

export const workflowInitialState = {
  prepare: { source: "manual", planText: "", commandsText: "", walls: [], rawPath: [] },
  align: { alignment: null, controlPoints: [] },
  plan: { planReady: false, simulation: null },
  execute: { jobId: "", runState: STAGE.BLOCKED, lastEvent: null, serialResult: null, error: "" },
};

export function workflowReducer(state, action) {
  switch (action.type) {
    case "prepare/update":
      return { ...state, prepare: { ...state.prepare, ...action.payload } };
    case "align/update":
      return { ...state, align: { ...state.align, ...action.payload } };
    case "plan/update":
      return { ...state, plan: { ...state.plan, ...action.payload } };
    case "execute/update":
      return { ...state, execute: { ...state.execute, ...action.payload } };
    case "reset":
      return workflowInitialState;
    default:
      return state;
  }
}

export function deriveWorkflowMeta(snapshot) {
  return {
    readiness: readinessFromSnapshot(snapshot),
    nextStep: nextStepFromSnapshot(snapshot),
  };
}
