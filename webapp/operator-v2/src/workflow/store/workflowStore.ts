import { create } from "zustand";
import type { OperatorStage } from "../model/stages";
import type {
  AnalyzeYaniti,
  ExportYaniti,
  HizalamaYaniti,
} from "../../data/services/operatorService";

export type PlanKaynakTuru = "dxf" | "dwg" | "json" | "manuel";

export interface PlanHazirligi {
  kaynakTuru: PlanKaynakTuru;
  kaynakEtiketi: string;
  endpoint: string;
  girdiAdi: string;
  durum: "hazir" | "hata";
  mesaj: string;
  komutMetni: string;
  planMetni: string;
  duvarlar: number[][];
  yolNoktalari: number[][];
  uyarilar: string[];
  onerilenAdimBoyutu?: number;
}

export interface HizalamaKontrolNoktasi {
  cad_x: number;
  cad_y: number;
  site_x: number;
  site_y: number;
  label: string;
  weight?: number;
}

export interface HizalamaDurumu {
  endpoint: string;
  toleranceM: number;
  kontrolNoktalari: HizalamaKontrolNoktasi[];
  mesaj: string;
  durum: "hazir" | "dikkat" | "hata";
  yanit: HizalamaYaniti;
  guncellenmeZamani: number;
}

export interface KontrolDurumu {
  endpoint: string;
  mesaj: string;
  durum: "hazir" | "dikkat" | "hata";
  yanit: AnalyzeYaniti;
  guncellenmeZamani: number;
}

export interface SonucCiktisi {
  endpoint: string;
  format: "robot_v1" | "gcode_lite";
  mesaj: string;
  durum: "hazir" | "dikkat" | "hata";
  yanit: ExportYaniti;
  guncellenmeZamani: number;
}

export interface CalistirmaOzeti {
  kip: string;
  faz: string;
  ton: string;
  baslik: string;
  mesaj: string;
  jobId: string | null;
  komutSayisi: number;
  artifactYollari: string[];
  notlar: string[];
  guncellenmeZamani: number;
}

export interface SimulationDurumu {
  isPlaying: boolean;
  progress: number;
  currentIndex: number;
  speed: number;
}

interface WorkflowState {
  aktifAsama: OperatorStage;
  hataMesaji: string;
  planHazirligi: PlanHazirligi | null;
  hizalamaDurumu: HizalamaDurumu | null;
  kontrolDurumu: KontrolDurumu | null;
  sonucCiktisi: SonucCiktisi | null;
  calistirmaOzeti: CalistirmaOzeti | null;
  simulation: SimulationDurumu;
  setAktifAsama: (asama: OperatorStage) => void;
  setHataMesaji: (mesaj: string) => void;
  setPlanHazirligi: (planHazirligi: PlanHazirligi | null) => void;
  setHizalamaDurumu: (hizalamaDurumu: HizalamaDurumu | null) => void;
  setKontrolDurumu: (kontrolDurumu: KontrolDurumu | null) => void;
  setSonucCiktisi: (sonucCiktisi: SonucCiktisi | null) => void;
  setCalistirmaOzeti: (calistirmaOzeti: CalistirmaOzeti | null) => void;
  setSimulation: (simulation: Partial<SimulationDurumu>) => void;
  sifirlaSimulation: () => void;
  sifirla: () => void;
}

const initialSimulation: SimulationDurumu = {
  isPlaying: false,
  progress: 0,
  currentIndex: 0,
  speed: 1,
};

const initialState = {
  aktifAsama: "plan-yukle" as OperatorStage,
  hataMesaji: "",
  planHazirligi: null as PlanHazirligi | null,
  hizalamaDurumu: null as HizalamaDurumu | null,
  kontrolDurumu: null as KontrolDurumu | null,
  sonucCiktisi: null as SonucCiktisi | null,
  calistirmaOzeti: null as CalistirmaOzeti | null,
  simulation: initialSimulation,
};

export const useWorkflowStore = create<WorkflowState>((set) => ({
  ...initialState,
  setAktifAsama: (aktifAsama) => set({ aktifAsama }),
  setHataMesaji: (hataMesaji) => set({ hataMesaji }),
  setPlanHazirligi: (planHazirligi) => set({ planHazirligi }),
  setHizalamaDurumu: (hizalamaDurumu) => set({ hizalamaDurumu }),
  setKontrolDurumu: (kontrolDurumu) => set({ kontrolDurumu }),
  setSonucCiktisi: (sonucCiktisi) => set({ sonucCiktisi }),
  setCalistirmaOzeti: (calistirmaOzeti) => set({ calistirmaOzeti }),
  setSimulation: (simulation) =>
    set((state) => ({
      simulation: {
        ...state.simulation,
        ...simulation,
      },
    })),
  sifirlaSimulation: () => set({ simulation: initialSimulation }),
  sifirla: () => set(initialState)
}));
