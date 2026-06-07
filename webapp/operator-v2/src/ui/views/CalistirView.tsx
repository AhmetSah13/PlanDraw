import React, { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { COPY } from "../../content";
import { ApiError } from "../../data/http/apiClient";
import {
  analyzeCommands,
  buildSimulationStreamUrl,
  createSimulationJob,
  executeSerialRun,
  stopLiveSerialExecution,
  stopSimulationJob,
  type AnalyzeYaniti,
} from "../../data/services/operatorService";
import {
  applySerialRunResult,
  applySimulationStreamEvent,
  attachSimulationJob,
  createInitialExecutionSnapshot,
  isJobNotFoundMessage,
  isLiveSerialExecutionActive,
  markLiveSerialStopStarting,
  markLiveSerialStopSuccess,
  markReconnectStarting,
  markRequestFailure,
  markSerialRunStarting,
  markSimulationStarting,
  markStopMissing,
  markStopStarting,
  markStopSuccess,
  markStreamDisconnected,
  type ExecutionSnapshot,
  type TechnicalEntry,
} from "../../lifecycle/execution/executionLifecycle";
import {
  getLiveSerialGate,
  type LiveSerialGateReason,
} from "../../lifecycle/execution/serialSafety";
import { useWorkflowStore } from "../../workflow/store/workflowStore";
import { SimulationPlayer } from "../components/SimulationPlayer";

function formatCoordinate(value?: number) {
  if (typeof value !== "number") {
    return "—";
  }

  return value.toFixed(3);
}

function formatMetric(value?: number) {
  if (typeof value !== "number") {
    return "—";
  }

  return value.toFixed(2);
}

function formatTechnicalDetail(entry: TechnicalEntry) {
  return `${entry.etiket}: ${entry.detay}`;
}

function analyzeBlocksLive(yanit: AnalyzeYaniti) {
  return Boolean(
    yanit.blocked ||
      yanit.parser.length ||
      yanit.analysis.length ||
      (yanit.stats.collision_count ?? 0) > 0 ||
      (yanit.stats.wall_proper_cross_count ?? 0) > 0,
  );
}

function resolveApiStopMessage(error: ApiError) {
  if (typeof error.data === "object" && error.data !== null) {
    const payload = error.data as Record<string, unknown>;
    if (typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }
  }

  return COPY.ekranlar.calistir.mesajlar.canliStopBasarisiz;
}

function liveGateMessage(reason: LiveSerialGateReason) {
  const mesajlar = COPY.ekranlar.calistir.mesajlar;
  if (reason === "plan-yok") {
    return mesajlar.planHazirDegil;
  }
  if (reason === "hizalama-yok") {
    return mesajlar.canliHizalamaYok;
  }
  if (reason === "hizalama-riskli") {
    return mesajlar.canliHizalamaRiskli;
  }
  if (reason === "kontrol-yok") {
    return mesajlar.canliKontrolYok;
  }
  if (reason === "kontrol-blocked") {
    return mesajlar.canliKontrolBlocked;
  }
  if (reason === "kontrol-bulgusu") {
    return mesajlar.canliKontrolBulgusu;
  }
  if (reason === "carpisma-riski") {
    return mesajlar.canliCarpismaRiski;
  }
  if (reason === "onay-yok") {
    return mesajlar.canliCalistirmaEngelli;
  }
  return mesajlar.canliHazir;
}

export function CalistirView() {
  const planHazirligi = useWorkflowStore((state) => state.planHazirligi);
  const hizalamaDurumu = useWorkflowStore((state) => state.hizalamaDurumu);
  const kontrolDurumu = useWorkflowStore((state) => state.kontrolDurumu);
  const setAktifAsama = useWorkflowStore((state) => state.setAktifAsama);
  const setCalistirmaOzeti = useWorkflowStore((state) => state.setCalistirmaOzeti);
  const simulation = useWorkflowStore((state) => state.simulation);
  const setSimulation = useWorkflowStore((state) => state.setSimulation);
  const sifirlaSimulation = useWorkflowStore((state) => state.sifirlaSimulation);

  const planHazir = Boolean(planHazirligi?.komutMetni?.trim());
  const [canliOnay, setCanliOnay] = useState(false);
  const [snapshot, setSnapshot] = useState<ExecutionSnapshot>(() =>
    createInitialExecutionSnapshot({
      planHazir,
      girdiAdi: planHazirligi?.girdiAdi,
    }),
  );
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setAktifAsama("calistir");
  }, [setAktifAsama]);

  useEffect(() => {
    if (!planHazir && eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSnapshot(
      createInitialExecutionSnapshot({
        planHazir,
        girdiAdi: planHazirligi?.girdiAdi,
      }),
    );
    sifirlaSimulation();
  }, [planHazir, planHazirligi?.girdiAdi, sifirlaSimulation]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    setCalistirmaOzeti({
      kip: snapshot.kip,
      faz: snapshot.faz,
      ton: snapshot.ton,
      baslik: snapshot.baslik,
      mesaj: snapshot.mesaj,
      jobId: snapshot.jobId,
      komutSayisi: snapshot.serialSonucu?.command_count ?? 0,
      artifactYollari: snapshot.serialSonucu?.artifact_paths ?? [],
      notlar: snapshot.serialSonucu?.notes ?? [],
      guncellenmeZamani: snapshot.guncellenmeZamani,
    });
  }, [setCalistirmaOzeti, snapshot]);

  const bindStream = (jobId: string, reconnect = false) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    if (reconnect) {
      setSnapshot((current) => markReconnectStarting(current));
    }

    const stream = new EventSource(buildSimulationStreamUrl(jobId));
    eventSourceRef.current = stream;

    stream.onopen = () => {
      setSnapshot((current) => attachSimulationJob(current, jobId));
    };

    stream.addEventListener("tick", (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as Record<string, unknown>;
      setSnapshot((current) => applySimulationStreamEvent(current, "tick", payload));
    });

    stream.addEventListener("done", (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as Record<string, unknown>;
      setSnapshot((current) => applySimulationStreamEvent(current, "done", payload));
      stream.close();
      eventSourceRef.current = null;
    });

    stream.addEventListener("ping", () => {
      setSnapshot((current) => applySimulationStreamEvent(current, "ping"));
    });

    stream.addEventListener("error", (event) => {
      const payload = JSON.parse((event as MessageEvent<string>).data) as Record<string, unknown>;
      setSnapshot((current) => applySimulationStreamEvent(current, "error", payload));

      const message = typeof payload.message === "string" ? payload.message : "";
      if (isJobNotFoundMessage(message)) {
        stream.close();
        eventSourceRef.current = null;
      }
    });

    stream.onerror = () => {
      setSnapshot((current) => markStreamDisconnected(current));
    };
  };

  const simulationMutation = useMutation({
    mutationFn: async () => {
      if (!planHazirligi?.komutMetni?.trim()) {
        throw new Error(COPY.ekranlar.calistir.mesajlar.planHazirDegil);
      }

      return createSimulationJob(planHazirligi.komutMetni, {
        walls: planHazirligi.duvarlar,
      });
    },
    onMutate: () => {
      setSimulation({ isPlaying: true });
      setSnapshot((current) => markSimulationStarting(current));
    },
    onSuccess: ({ job_id }) => {
      setSnapshot((current) => attachSimulationJob(current, job_id));
      bindStream(job_id);
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : COPY.geriBildirim.hata.genel;
      setSnapshot((current) =>
        markRequestFailure(current, message, COPY.ekranlar.calistir.teknik.jobKaydi),
      );
    },
  });

  const liveSerialStopMutation = useMutation({
    mutationFn: async () => stopLiveSerialExecution(),
    onMutate: () => {
      setSnapshot((current) => markLiveSerialStopStarting(current));
    },
    onSuccess: (result) => {
      if (result.ok === false || result.stopped === false) {
        const message =
          result.message || COPY.ekranlar.calistir.mesajlar.canliStopBasarisiz;
        setSnapshot((current) =>
          markRequestFailure(
            current,
            message,
            COPY.ekranlar.calistir.teknik.canliStop,
          ),
        );
        return;
      }

      setSnapshot((current) => markLiveSerialStopSuccess(current));
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? resolveApiStopMessage(error)
          : error instanceof Error
            ? error.message
            : COPY.ekranlar.calistir.mesajlar.canliStopBasarisiz;
      setSnapshot((current) =>
        markRequestFailure(
          current,
          message,
          COPY.ekranlar.calistir.teknik.canliStop,
        ),
      );
    },
  });

  const stopMutation = useMutation({
    mutationFn: async () => {
      if (!snapshot.jobId) {
        throw new Error(COPY.ekranlar.calistir.mesajlar.jobBulunamadi);
      }

      return stopSimulationJob(snapshot.jobId);
    },
    onMutate: () => {
      setSnapshot((current) => markStopStarting(current));
    },
    onSuccess: () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      setSnapshot((current) => markStopSuccess(current));
    },
    onError: (error) => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      if (error instanceof ApiError && error.status === 404) {
        setSnapshot((current) => markStopMissing(current));
        return;
      }

      const message = error instanceof Error ? error.message : COPY.geriBildirim.hata.genel;
      setSnapshot((current) =>
        markRequestFailure(current, message, COPY.ekranlar.calistir.teknik.stop),
      );
    },
  });

  const serialMutation = useMutation({
    mutationFn: async (dryRun: boolean) => {
      if (!planHazirligi?.komutMetni?.trim()) {
        throw new Error(COPY.ekranlar.calistir.mesajlar.planHazirDegil);
      }

      if (!dryRun) {
        const gate = getLiveSerialGate({
          planHazirligi,
          hizalamaDurumu,
          kontrolDurumu,
          canliOnay,
        });

        if (!gate.allowed) {
          throw new Error(liveGateMessage(gate.reason));
        }
      }

      let livePreflight = kontrolDurumu?.yanit;
      if (!dryRun) {
        livePreflight = await analyzeCommands(
          planHazirligi.komutMetni,
          planHazirligi.duvarlar,
          "error",
        );

        if (analyzeBlocksLive(livePreflight)) {
          throw new Error(COPY.ekranlar.calistir.mesajlar.canliFinalKontrolBlocked);
        }
      }

      return executeSerialRun(planHazirligi.komutMetni, {
        dryRun,
        walls: dryRun ? undefined : planHazirligi.duvarlar,
        preflight: dryRun ? undefined : livePreflight,
      });
    },
    onMutate: (dryRun) => {
      setSnapshot((current) =>
        markSerialRunStarting(current, dryRun ? "serial-on-kontrol" : "serial-canli"),
      );
    },
    onSuccess: (result, dryRun) => {
      setSnapshot((current) =>
        applySerialRunResult(current, result, dryRun ? "serial-on-kontrol" : "serial-canli"),
      );
    },
    onError: (error, dryRun) => {
      const message = error instanceof Error ? error.message : COPY.geriBildirim.hata.genel;
      setSnapshot((current) =>
        markRequestFailure(
          current,
          message,
          dryRun ? COPY.ekranlar.calistir.teknik.serial : COPY.ekranlar.calistir.teknik.serial,
        ),
      );
    },
  });

  const aktifSimulasyonVar =
    snapshot.faz === "baslatiliyor" ||
    snapshot.faz === "izleniyor" ||
    snapshot.faz === "yenidenBaglaniyor" ||
    snapshot.faz === "durduruluyor";

  const dryRunEngelli =
    !planHazir || aktifSimulasyonVar || serialMutation.isPending || simulationMutation.isPending;
  const liveSerialGate = getLiveSerialGate({
    planHazirligi,
    hizalamaDurumu,
    kontrolDurumu,
    canliOnay,
  });
  const canliSeriEngelli = dryRunEngelli || !liveSerialGate.allowed;
  const canliGateMesaji = liveGateMessage(liveSerialGate.reason);
  const canliSerialStopAktif =
    isLiveSerialExecutionActive(snapshot) && serialMutation.isPending;
  const canliSerialStopEngelli =
    !canliSerialStopAktif ||
    liveSerialStopMutation.isPending ||
    stopMutation.isPending;

  const sonTick = snapshot.sonTick;

  return (
    <section className="execute-page">
      <header className="execute-page__hero">
        <div>
          <p className="execute-page__eyebrow">{COPY.ekranlar.calistir.akisSecimBasligi}</p>
          <h2>{COPY.ekranlar.calistir.ustBaslik}</h2>
          <p className="execute-page__intro">{COPY.ekranlar.calistir.ustAciklama}</p>
        </div>
        <div className={`execute-status execute-status--${snapshot.ton}`}>
          <span className="execute-status__label">{COPY.ekranlar.calistir.durumKartBasligi}</span>
          <strong>{snapshot.baslik}</strong>
          <p>{snapshot.mesaj}</p>
        </div>
      </header>

      <section className="execute-summary">
        <div className="execute-summary__card">
          <span>{COPY.ekranlar.calistir.planOzetiBaslik}</span>
          <strong>{planHazirligi?.girdiAdi ?? COPY.asamalar.planYukle.baslik}</strong>
          <p>{COPY.ekranlar.calistir.planOzetiAciklama}</p>
        </div>
        <div className="execute-summary__card">
          <span>{COPY.ortak.calistirilabilirGirdi}</span>
          <strong>{planHazir ? COPY.durumlar.hazir : COPY.durumlar.engelli}</strong>
          <p>
            {planHazir
              ? COPY.ekranlar.calistir.sonrakiAdimHazir
              : COPY.ekranlar.calistir.sonrakiAdimEngelli}
          </p>
        </div>
        <div className="execute-summary__card">
          <span>{COPY.ortak.jobKimligi}</span>
          <strong>{snapshot.jobId ?? "Henüz yok"}</strong>
          <p>
            {snapshot.jobId
              ? "/api/jobs/{id}/stream üzerinden izleniyor."
              : "Aktif simülasyon başlatıldığında job kimliği burada görünür."}
          </p>
        </div>
      </section>

      <section className="execute-workspace">
        <div className="execute-main">
          <div className="execute-flow-grid">
            <article className="execute-card">
              <div className="execute-card__header">
                <div>
                  <span className="execute-chip execute-chip--safe">
                    {COPY.ekranlar.calistir.guvenliRozet}
                  </span>
                  <h3>{COPY.ekranlar.calistir.simulasyonBaslik}</h3>
                </div>
                <p>{COPY.ekranlar.calistir.simulasyonAciklama}</p>
              </div>

              <div className="execute-card__actions">
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => {
                    setSimulation({ isPlaying: true });
                    simulationMutation.mutate();
                  }}
                  disabled={!planHazir || simulationMutation.isPending || aktifSimulasyonVar}
                >
                  {snapshot.canRetry &&
                  (snapshot.faz === "tamamlandi" ||
                    snapshot.faz === "hata" ||
                    snapshot.faz === "durduruldu")
                    ? COPY.butonlar.simulasyonuYenidenBaslat
                    : COPY.butonlar.simulasyonuBaslat}
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => snapshot.jobId && bindStream(snapshot.jobId, true)}
                  disabled={!snapshot.jobId || stopMutation.isPending}
                >
                  {COPY.butonlar.yenidenBaglan}
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => stopMutation.mutate()}
                  disabled={!snapshot.canStop || stopMutation.isPending}
                >
                  {COPY.butonlar.isiDurdur}
                </button>
              </div>

              <div className="execute-inline-grid">
                <div>
                  <span>{COPY.ekranlar.calistir.kartlar.simulasyonDurumu}</span>
                  <strong>{snapshot.baslik}</strong>
                </div>
                <div>
                  <span>{COPY.ortak.sonMesaj}</span>
                  <strong>{snapshot.mesaj}</strong>
                </div>
              </div>

              <p className="execute-local-note">
                Bu paneldeki animasyon yerel önizlemedir. Gerçek backend job durumu üstteki ana durum kartı
                ve iş kimliği alanından izlenir.
              </p>
            </article>

            <article className="execute-card execute-card--risk">
              <div className="execute-card__header">
                <div>
                  <span className="execute-chip execute-chip--risk">
                    {COPY.ekranlar.calistir.riskRozeti}
                  </span>
                  <h3>{COPY.ekranlar.calistir.canliBaslik}</h3>
                </div>
                <p>{COPY.ekranlar.calistir.canliAciklama}</p>
              </div>

              <div className="execute-safe-check">
                <div>
                  <strong>{COPY.ekranlar.calistir.onKontrolBaslik}</strong>
                  <p>{COPY.ekranlar.calistir.onKontrolAciklama}</p>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => serialMutation.mutate(true)}
                  disabled={dryRunEngelli}
                >
                  {COPY.butonlar.onKontrolCalistir}
                </button>
              </div>

              <label className="execute-risk-consent">
                <input
                  type="checkbox"
                  checked={canliOnay}
                  onChange={(event) => setCanliOnay(event.target.checked)}
                />
                <span>
                  <strong>{COPY.ekranlar.calistir.canliOnayEtiketi}</strong>
                  <small>{COPY.ekranlar.calistir.canliOnayAciklamasi}</small>
                </span>
              </label>

              {!liveSerialGate.allowed && !dryRunEngelli ? (
                <p className="execute-inline-warning">
                  {canliGateMesaji}
                </p>
              ) : null}

              {aktifSimulasyonVar ? (
                <p className="execute-inline-warning">
                  {COPY.ekranlar.calistir.mesajlar.aktifSimulasyonVar}
                </p>
              ) : null}

              <div className="execute-card__actions">
                <button
                  className="danger-button"
                  type="button"
                  onClick={() => serialMutation.mutate(false)}
                  disabled={canliSeriEngelli || liveSerialStopMutation.isPending}
                >
                  {COPY.butonlar.canliCalistir}
                </button>
                {canliSerialStopAktif ? (
                  <button
                    className="danger-button"
                    type="button"
                    onClick={() => liveSerialStopMutation.mutate()}
                    disabled={canliSerialStopEngelli}
                  >
                    {liveSerialStopMutation.isPending
                      ? COPY.ekranlar.calistir.mesajlar.canliStopGonderiliyor
                      : COPY.butonlar.canliSerialStop}
                  </button>
                ) : null}
              </div>

              <p className="execute-inline-warning">{COPY.ekranlar.calistir.canliStopUyari}</p>
            </article>
          </div>

          <article className="execute-status-card">
            <div className="execute-status-card__header">
              <div>
                <p className="execute-page__eyebrow">Simülasyon</p>
                <h3>Plan yolu adım adım önizleme</h3>
              </div>
            </div>
            <SimulationPlayer
              points={planHazirligi?.yolNoktalari ?? []}
              walls={planHazirligi?.duvarlar ?? []}
              state={simulation}
              onStateChange={(next) => setSimulation(next)}
            />
          </article>

          <article className="execute-status-card">
            <div className="execute-status-card__header">
              <div>
                <p className="execute-page__eyebrow">{COPY.ekranlar.calistir.kartlar.siradakiAdim}</p>
                <h3>{snapshot.baslik}</h3>
              </div>
              <span className={`execute-tone execute-tone--${snapshot.ton}`}>Backend durum akışı</span>
            </div>
            <p className="execute-status-card__text">{snapshot.mesaj}</p>

            <div className="execute-metrics">
              <div>
                <span>Süre</span>
                <strong>{formatMetric(sonTick?.t)}</strong>
              </div>
              <div>
                <span>X</span>
                <strong>{formatCoordinate(sonTick?.x)}</strong>
              </div>
              <div>
                <span>Y</span>
                <strong>{formatCoordinate(sonTick?.y)}</strong>
              </div>
              <div>
                <span>Maks. hata</span>
                <strong>{formatMetric(sonTick?.error_max)}</strong>
              </div>
            </div>
          </article>
        </div>

        <aside className="execute-side">
          <div className={`execute-readiness execute-readiness--${snapshot.ton}`}>
            <span>{COPY.ortak.hazirOlmaDurumu}</span>
            <strong>{snapshot.baslik}</strong>
            <p>{snapshot.mesaj}</p>
          </div>

          <div className="execute-next">
            <span>{COPY.ortak.sonrakiAdim}</span>
            <strong>
              {planHazir ? COPY.ekranlar.calistir.kartlar.siradakiAdim : COPY.asamalar.planYukle.baslik}
            </strong>
            <p>
              {planHazir
                ? COPY.ekranlar.calistir.sonrakiAdimHazir
                : COPY.ekranlar.calistir.sonrakiAdimEngelli}
            </p>
          </div>

          <details className="execute-tech">
            <summary>{COPY.ekranlar.calistir.kartlar.teknikDetaylar}</summary>
            <div className="execute-tech__body">
              <div>
                <span>{COPY.ortak.endpointBilgisi}</span>
                <strong>/api/jobs · /api/jobs/{'{'}id{'}'}/stream · /api/jobs/{'{'}id{'}'}/stop · /api/execute_serial · /api/execute_serial/stop</strong>
              </div>
              <div>
                <span>{COPY.ortak.riskSeviyesi}</span>
                <strong>{snapshot.kip === "serial-canli" ? COPY.ekranlar.calistir.riskRozeti : COPY.ekranlar.calistir.guvenliRozet}</strong>
              </div>
              <div>
                <span>{COPY.ortak.jobKimligi}</span>
                <strong>{snapshot.jobId ?? "Yok"}</strong>
              </div>
              <div>
                <span>{COPY.ortak.komutSayisi}</span>
                <strong>{snapshot.serialSonucu?.command_count ?? "—"}</strong>
              </div>
              {snapshot.serialSonucu?.notes?.length ? (
                <div className="execute-tech__notes">
                  <span>{COPY.ortak.notlar}</span>
                  <ul>
                    {snapshot.serialSonucu.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {snapshot.teknikKayitlar.length ? (
                <div className="execute-tech__notes">
                  <span>{COPY.ortak.teknikAkis}</span>
                  <ul>
                    {snapshot.teknikKayitlar.map((entry) => (
                      <li key={entry.id}>{formatTechnicalDetail(entry)}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </details>
        </aside>
      </section>
    </section>
  );
}
