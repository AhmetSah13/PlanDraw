import { useCallback, useMemo, useRef, useState } from "react";
import { executeService } from "../data/services.js";

export function normalizeStreamEvent(raw) {
  if (!raw || typeof raw !== "object") return { phase: "unknown", message: "Bilinmeyen event", raw };
  return {
    phase: raw.phase ?? raw.status ?? "unknown",
    message: raw.message ?? raw.detail ?? "Mesaj yok",
    progress: Number.isFinite(raw.progress) ? raw.progress : null,
    at: Date.now(),
    raw,
  };
}

export function useExecutionLifecycle({ onEvent, onStateChange }) {
  const sourceRef = useRef(null);
  const lastJobIdRef = useRef("");
  const [streamState, setStreamState] = useState("idle");
  const [lastError, setLastError] = useState("");

  const updateState = useCallback(
    (next, err = "") => {
      setStreamState(next);
      setLastError(err);
      onStateChange?.(next, err);
    },
    [onStateChange],
  );

  const stop = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    updateState("stopped");
  }, [updateState]);

  const connect = useCallback(
    (jobId) => {
      if (!jobId) return;
      stop();
      lastJobIdRef.current = jobId;
      updateState("connecting");
      const source = new EventSource(executeService.streamUrl(jobId));
      sourceRef.current = source;

      source.onopen = () => updateState("running");
      source.onerror = () => updateState("error", "Stream bağlantısı koptu");
      source.onmessage = (event) => {
        try {
          const raw = JSON.parse(event.data);
          const normalized = normalizeStreamEvent(raw);
          onEvent?.(normalized);
          if (["done", "finished", "completed"].includes(normalized.phase)) {
            updateState("done");
            source.close();
            sourceRef.current = null;
          }
        } catch {
          updateState("error", "Stream event parse hatası");
        }
      };
    },
    [onEvent, stop, updateState],
  );

  const reconnect = useCallback(() => {
    if (!lastJobIdRef.current) return;
    connect(lastJobIdRef.current);
  }, [connect]);

  const retry = useCallback(() => {
    reconnect();
  }, [reconnect]);

  const recover = useCallback(() => {
    setLastError("");
    reconnect();
  }, [reconnect]);

  return useMemo(
    () => ({
      streamState,
      lastError,
      start: connect,
      stop,
      reconnect,
      retry,
      recover,
    }),
    [connect, lastError, reconnect, recover, retry, stop, streamState],
  );
}
