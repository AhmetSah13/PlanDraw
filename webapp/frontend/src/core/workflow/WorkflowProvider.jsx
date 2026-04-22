import React, { createContext, useContext, useMemo, useReducer } from "react";
import { deriveWorkflowMeta, workflowInitialState, workflowReducer, WORKFLOW_STORAGE_KEY } from "./workflowMachine.js";

function loadState() {
  try {
    const raw = sessionStorage.getItem(WORKFLOW_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

const WorkflowContext = createContext(null);

export function WorkflowProvider({ children }) {
  const [state, dispatch] = useReducer(workflowReducer, loadState() ?? workflowInitialState);

  React.useEffect(() => {
    sessionStorage.setItem(WORKFLOW_STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const value = useMemo(() => {
    const { readiness, nextStep } = deriveWorkflowMeta(state);
    return {
      state,
      readiness,
      nextStep,
      updatePrepare: (payload) => dispatch({ type: "prepare/update", payload }),
      updateAlign: (payload) => dispatch({ type: "align/update", payload }),
      updatePlan: (payload) => dispatch({ type: "plan/update", payload }),
      updateExecute: (payload) => dispatch({ type: "execute/update", payload }),
      resetWorkflow: () => dispatch({ type: "reset" }),
    };
  }, [state]);

  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>;
}

export function useWorkflow() {
  const ctx = useContext(WorkflowContext);
  if (!ctx) throw new Error("WorkflowProvider gerekli");
  return ctx;
}
