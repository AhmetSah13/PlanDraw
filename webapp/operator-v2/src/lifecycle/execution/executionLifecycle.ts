import { COPY } from "../../content";
import type { SerialCalistirmaYaniti } from "../../data/services/operatorService";

export type ExecutionMode = "simulasyon" | "serial-on-kontrol" | "serial-canli";
export type ExecutionTone =
  | "bekliyor"
  | "hazir"
  | "calisiyor"
  | "tamamlandi"
  | "hata"
  | "dikkat";
export type ExecutionPhase =
  | "engelli"
  | "hazir"
  | "baslatiliyor"
  | "izleniyor"
  | "yenidenBaglaniyor"
  | "durduruluyor"
  | "durduruldu"
  | "tamamlandi"
  | "bulunamadi"
  | "hata";

export interface ExecutionTick {
  t?: number;
  x?: number;
  y?: number;
  error?: number;
  error_mean?: number;
  error_max?: number;
  index?: number;
  finished?: boolean;
}

export interface TechnicalEntry {
  id: string;
  etiket: string;
  detay: string;
  ton: "bilgi" | "uyari" | "hata";
}

export interface ExecutionSnapshot {
  kip: ExecutionMode;
  faz: ExecutionPhase;
  ton: ExecutionTone;
  baslik: string;
  mesaj: string;
  jobId: string | null;
  planHazir: boolean;
  canStop: boolean;
  canReconnect: boolean;
  canRetry: boolean;
  sonTick: ExecutionTick | null;
  serialSonucu: SerialCalistirmaYaniti | null;
  teknikKayitlar: TechnicalEntry[];
  guncellenmeZamani: number;
}

export interface ExecutionSnapshotInput {
  planHazir: boolean;
  girdiAdi?: string;
}

interface StreamPayload extends Record<string, unknown> {
  message?: string;
}

function teknikKayitEkle(
  previous: ExecutionSnapshot,
  etiket: string,
  detay: string,
  ton: TechnicalEntry["ton"] = "bilgi",
): TechnicalEntry[] {
  const kayit: TechnicalEntry = {
    id: `${Date.now()}-${previous.teknikKayitlar.length}`,
    etiket,
    detay,
    ton,
  };

  return [kayit, ...previous.teknikKayitlar].slice(0, 8);
}

function patchSnapshot(
  previous: ExecutionSnapshot,
  next: Partial<ExecutionSnapshot>,
  teknik?: {
    etiket: string;
    detay: string;
    ton?: TechnicalEntry["ton"];
  },
): ExecutionSnapshot {
  return {
    ...previous,
    ...next,
    teknikKayitlar: teknik
      ? teknikKayitEkle(previous, teknik.etiket, teknik.detay, teknik.ton)
      : previous.teknikKayitlar,
    guncellenmeZamani: Date.now(),
  };
}

function isPositiveNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function normalizeStatusTitle(ton: ExecutionTone) {
  if (ton === "hazir") {
    return COPY.durumlar.hazir;
  }
  if (ton === "calisiyor") {
    return COPY.durumlar.calisiyor;
  }
  if (ton === "tamamlandi") {
    return COPY.durumlar.tamamlandi;
  }
  if (ton === "hata") {
    return COPY.durumlar.hata;
  }
  if (ton === "dikkat") {
    return COPY.durumlar.dikkat;
  }
  return COPY.durumlar.bekliyor;
}

export function isJobNotFoundMessage(value: unknown) {
  return typeof value === "string" && value.toLowerCase().includes("job not found");
}

export function createInitialExecutionSnapshot(
  input: ExecutionSnapshotInput = { planHazir: false },
): ExecutionSnapshot {
  if (!input.planHazir) {
    return {
      kip: "simulasyon",
      faz: "engelli",
      ton: "dikkat",
      baslik: COPY.durumlar.engelli,
      mesaj: COPY.ekranlar.calistir.mesajlar.planHazirDegil,
      jobId: null,
      planHazir: false,
      canStop: false,
      canReconnect: false,
      canRetry: false,
      sonTick: null,
      serialSonucu: null,
      teknikKayitlar: [],
      guncellenmeZamani: Date.now(),
    };
  }

  return {
    kip: "simulasyon",
    faz: "hazir",
    ton: "hazir",
    baslik: COPY.durumlar.hazir,
    mesaj: input.girdiAdi
      ? COPY.ekranlar.calistir.mesajlar.planHazir(input.girdiAdi)
      : COPY.ekranlar.calistir.mesajlar.planHazirVarsayilan,
    jobId: null,
    planHazir: true,
    canStop: false,
    canReconnect: false,
    canRetry: true,
    sonTick: null,
    serialSonucu: null,
    teknikKayitlar: [],
    guncellenmeZamani: Date.now(),
  };
}

export function updateExecutionSnapshot(
  previous: ExecutionSnapshot,
  nextPhase: ExecutionPhase,
  message: string,
): ExecutionSnapshot {
  const tone: ExecutionTone =
    nextPhase === "hazir"
      ? "hazir"
      : nextPhase === "tamamlandi"
        ? "tamamlandi"
        : nextPhase === "hata"
          ? "hata"
          : nextPhase === "bulunamadi" || nextPhase === "engelli" || nextPhase === "durduruldu"
            ? "dikkat"
            : "calisiyor";

  return patchSnapshot(previous, {
    faz: nextPhase,
    ton: tone,
    baslik: normalizeStatusTitle(tone),
    mesaj: message,
  });
}

export function markSimulationStarting(previous: ExecutionSnapshot) {
  return patchSnapshot(
    previous,
    {
      kip: "simulasyon",
      faz: "baslatiliyor",
      ton: "calisiyor",
      baslik: COPY.durumlar.calisiyor,
      mesaj: COPY.ekranlar.calistir.mesajlar.simulasyonBaslatiliyor,
      jobId: null,
      canStop: false,
      canReconnect: false,
      canRetry: false,
      serialSonucu: null,
      sonTick: null,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.jobKaydi,
      detay: "/api/jobs isteği gönderildi.",
    },
  );
}

export function attachSimulationJob(previous: ExecutionSnapshot, jobId: string) {
  return patchSnapshot(
    previous,
    {
      kip: "simulasyon",
      faz: "izleniyor",
      ton: "calisiyor",
      baslik: COPY.durumlar.calisiyor,
      mesaj: COPY.ekranlar.calistir.mesajlar.simulasyonIzleniyor,
      jobId,
      canStop: true,
      canReconnect: true,
      canRetry: false,
      serialSonucu: null,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.jobKaydi,
      detay: `Job kimliği alındı: ${jobId}`,
    },
  );
}

export function markReconnectStarting(previous: ExecutionSnapshot) {
  return patchSnapshot(
    previous,
    {
      faz: "yenidenBaglaniyor",
      ton: "dikkat",
      baslik: COPY.durumlar.dikkat,
      mesaj: COPY.ekranlar.calistir.mesajlar.yenidenBaglaniyor,
      canStop: false,
      canReconnect: false,
      canRetry: false,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.stream,
      detay: "/api/jobs/{id}/stream bağlantısı yeniden kuruluyor.",
      ton: "uyari",
    },
  );
}

export function markStreamDisconnected(previous: ExecutionSnapshot) {
  return patchSnapshot(
    previous,
    {
      faz: "yenidenBaglaniyor",
      ton: "dikkat",
      baslik: COPY.durumlar.dikkat,
      mesaj: COPY.ekranlar.calistir.mesajlar.baglantiKoptu,
      canStop: Boolean(previous.jobId),
      canReconnect: Boolean(previous.jobId),
      canRetry: Boolean(previous.planHazir),
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.stream,
      detay: "Akış bağlantısı kesildi veya beklemeye geçti.",
      ton: "uyari",
    },
  );
}

export function applySimulationStreamEvent(
  previous: ExecutionSnapshot,
  eventType: "tick" | "done" | "error" | "ping",
  payload: StreamPayload = {},
) {
  if (eventType === "ping") {
    return patchSnapshot(
      previous,
      {},
      {
        etiket: COPY.ekranlar.calistir.teknik.stream,
        detay: "Akış canlı; sunucu ping ile bağlantıyı açık tutuyor.",
      },
    );
  }

  if (eventType === "tick") {
    const tick: ExecutionTick = {
      t: isPositiveNumber(payload.t) ? payload.t : undefined,
      x: isPositiveNumber(payload.x) ? payload.x : undefined,
      y: isPositiveNumber(payload.y) ? payload.y : undefined,
      error: isPositiveNumber(payload.error) ? payload.error : undefined,
      error_mean: isPositiveNumber(payload.error_mean) ? payload.error_mean : undefined,
      error_max: isPositiveNumber(payload.error_max) ? payload.error_max : undefined,
      index: isPositiveNumber(payload.index) ? payload.index : undefined,
      finished: typeof payload.finished === "boolean" ? payload.finished : undefined,
    };

    return patchSnapshot(
      previous,
      {
        faz: "izleniyor",
        ton: "calisiyor",
        baslik: COPY.durumlar.calisiyor,
        mesaj: COPY.ekranlar.calistir.mesajlar.simulasyonAkisiSuruyor,
        canStop: true,
        canReconnect: true,
        canRetry: false,
        sonTick: tick,
      },
      {
        etiket: COPY.ekranlar.calistir.teknik.sonOlay,
        detay:
          typeof tick.index === "number"
            ? `Adım ${tick.index} güncellendi.`
            : "Yeni simülasyon olayı alındı.",
      },
    );
  }

  if (eventType === "done") {
    const tick: ExecutionTick = {
      t: isPositiveNumber(payload.t) ? payload.t : undefined,
      x: isPositiveNumber(payload.x) ? payload.x : undefined,
      y: isPositiveNumber(payload.y) ? payload.y : undefined,
      error: isPositiveNumber(payload.error) ? payload.error : undefined,
      error_mean: isPositiveNumber(payload.error_mean) ? payload.error_mean : undefined,
      error_max: isPositiveNumber(payload.error_max) ? payload.error_max : undefined,
      finished: true,
    };

    return patchSnapshot(
      previous,
      {
        faz: "tamamlandi",
        ton: "tamamlandi",
        baslik: COPY.durumlar.tamamlandi,
        mesaj: COPY.ekranlar.calistir.mesajlar.simulasyonTamamlandi,
        canStop: false,
        canReconnect: false,
        canRetry: true,
        sonTick: tick,
      },
      {
        etiket: COPY.ekranlar.calistir.teknik.sonOlay,
        detay: "Simülasyon tamamlandı.",
      },
    );
  }

  const rawMessage = typeof payload.message === "string" ? payload.message : "";
  if (isJobNotFoundMessage(rawMessage)) {
    return patchSnapshot(
      previous,
      {
        faz: "bulunamadi",
        ton: "dikkat",
        baslik: COPY.durumlar.dikkat,
        mesaj: COPY.ekranlar.calistir.mesajlar.jobBulunamadi,
        canStop: false,
        canReconnect: true,
        canRetry: true,
      },
      {
        etiket: COPY.ekranlar.calistir.teknik.stream,
        detay: "İş artık bulunamadı; bu durum kırmızı hata yerine yaşam döngüsü bilgisi olarak işlendi.",
        ton: "uyari",
      },
    );
  }

  return patchSnapshot(
    previous,
    {
      faz: "hata",
      ton: "hata",
      baslik: COPY.durumlar.hata,
      mesaj: rawMessage || COPY.ekranlar.calistir.mesajlar.simulasyonHata,
      canStop: false,
      canReconnect: Boolean(previous.jobId),
      canRetry: true,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.sonOlay,
      detay: rawMessage || "Simülasyon akışında hata bildirildi.",
      ton: "hata",
    },
  );
}

export function markStopStarting(previous: ExecutionSnapshot) {
  return patchSnapshot(
    previous,
    {
      faz: "durduruluyor",
      ton: "dikkat",
      baslik: COPY.durumlar.dikkat,
      mesaj: COPY.ekranlar.calistir.mesajlar.durduruluyor,
      canStop: false,
      canReconnect: false,
      canRetry: false,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.stop,
      detay: "/api/jobs/{id}/stop isteği gönderildi.",
      ton: "uyari",
    },
  );
}

export function markStopSuccess(previous: ExecutionSnapshot) {
  return patchSnapshot(
    previous,
    {
      faz: "durduruldu",
      ton: "dikkat",
      baslik: COPY.durumlar.dikkat,
      mesaj: COPY.ekranlar.calistir.mesajlar.isDurduruldu,
      canStop: false,
      canReconnect: false,
      canRetry: true,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.stop,
      detay: "İş güvenli biçimde durduruldu.",
      ton: "uyari",
    },
  );
}

export function markStopMissing(previous: ExecutionSnapshot) {
  return patchSnapshot(
    previous,
    {
      faz: "bulunamadi",
      ton: "dikkat",
      baslik: COPY.durumlar.dikkat,
      mesaj: COPY.ekranlar.calistir.mesajlar.jobBulunamadi,
      canStop: false,
      canReconnect: false,
      canRetry: true,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.stop,
      detay: "Stop isteğinde iş bulunamadı; aktif olmayan oturum normal bilgi olarak işlendi.",
      ton: "uyari",
    },
  );
}

export function markRequestFailure(
  previous: ExecutionSnapshot,
  message: string,
  technicalLabel: string,
) {
  return patchSnapshot(
    previous,
    {
      faz: "hata",
      ton: "hata",
      baslik: COPY.durumlar.hata,
      mesaj: message,
      canStop: false,
      canReconnect: Boolean(previous.jobId),
      canRetry: Boolean(previous.planHazir),
    },
    {
      etiket: technicalLabel,
      detay: message,
      ton: "hata",
    },
  );
}

export function markSerialRunStarting(
  previous: ExecutionSnapshot,
  mode: "serial-on-kontrol" | "serial-canli",
) {
  const canlı = mode === "serial-canli";
  return patchSnapshot(
    previous,
    {
      kip: mode,
      faz: "baslatiliyor",
      ton: "calisiyor",
      baslik: COPY.durumlar.calisiyor,
      mesaj: canlı
        ? COPY.ekranlar.calistir.mesajlar.canliCalistirmaBaslatiliyor
        : COPY.ekranlar.calistir.mesajlar.onKontrolBaslatiliyor,
      canStop: false,
      canReconnect: false,
      canRetry: false,
      serialSonucu: null,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.serial,
      detay: canlı
        ? "/api/execute_serial dry_run=false isteği gönderildi."
        : "/api/execute_serial dry_run=true isteği gönderildi.",
    },
  );
}

export function applySerialRunResult(
  previous: ExecutionSnapshot,
  result: SerialCalistirmaYaniti,
  mode: "serial-on-kontrol" | "serial-canli",
) {
  const status = result.status.toLowerCase();
  const başarısız = status === "failed";
  const atlandı = status === "skipped";
  const tone: ExecutionTone = başarısız ? "hata" : atlandı ? "dikkat" : "tamamlandi";

  return patchSnapshot(
    previous,
    {
      kip: mode,
      faz: başarısız ? "hata" : atlandı ? "bulunamadi" : "tamamlandi",
      ton: tone,
      baslik: normalizeStatusTitle(tone),
      mesaj: result.message,
      canStop: false,
      canReconnect: false,
      canRetry: true,
      serialSonucu: result,
    },
    {
      etiket: COPY.ekranlar.calistir.teknik.serial,
      detay: `Yanıt alındı: ${result.status}`,
      ton: başarısız ? "hata" : atlandı ? "uyari" : "bilgi",
    },
  );
}
