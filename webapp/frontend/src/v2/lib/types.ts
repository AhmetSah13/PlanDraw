export type StageKey = "planYukle" | "hizala" | "kontrolEt" | "calistir" | "sonuclar";

export type Durum = "hazir" | "engelli" | "calisiyor" | "tamamlandi" | "hata";

export interface WorkflowDurum {
  stage: StageKey;
  durum: Durum;
  mesaj: string;
}

export interface AppState {
  planText: string;
  commandsText: string;
  walls: number[][];
  rawPathPoints: number[][];
  alignment: Record<string, unknown> | null;
  sonKontrol: { blocked: boolean; pathCount: number } | null;
  jobId: string;
  sonEvent: Record<string, unknown> | null;
  serialSonuc: Record<string, unknown> | null;
  hata: string;
}
