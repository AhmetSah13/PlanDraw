import { create } from "zustand";
import type { AppState } from "../lib/types";

interface WorkflowStore extends AppState {
  setHata: (hata: string) => void;
  merge: (patch: Partial<AppState>) => void;
  reset: () => void;
}

const initialState: AppState = {
  planText: "",
  commandsText: "",
  walls: [],
  rawPathPoints: [],
  alignment: null,
  sonKontrol: null,
  jobId: "",
  sonEvent: null,
  serialSonuc: null,
  hata: "",
};

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  ...initialState,
  setHata: (hata) => set({ hata }),
  merge: (patch) => set((s) => ({ ...s, ...patch })),
  reset: () => set(initialState),
}));
