import React, { useEffect, useMemo, useRef } from "react";
import { PlanCanvas } from "./PlanCanvas";

export interface SimulationState {
  isPlaying: boolean;
  progress: number;
  currentIndex: number;
  speed: number;
}

interface Props {
  points: number[][];
  walls?: number[][];
  state: SimulationState;
  onStateChange: (next: Partial<SimulationState>) => void;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export function SimulationPlayer({ points, walls, state, onStateChange }: Props) {
  const lastTs = useRef<number | null>(null);
  const pointCount = points.length;

  const speedOptions = useMemo(
    () => [
      { label: "1x", value: 1 },
      { label: "2x", value: 2 },
      { label: "5x", value: 5 },
    ],
    [],
  );

  useEffect(() => {
    if (!state.isPlaying || pointCount < 2) {
      lastTs.current = null;
      return;
    }

    const baseDurationMs = 9000;
    const duration = baseDurationMs / (state.speed || 1);
    let rafId = 0;

    const tick = (ts: number) => {
      if (lastTs.current == null) {
        lastTs.current = ts;
      }
      const delta = ts - lastTs.current;
      lastTs.current = ts;

      const progressStep = delta / duration;
      const nextProgress = clamp(state.progress + progressStep, 0, 1);
      const nextIndex = Math.min(pointCount - 1, Math.floor(nextProgress * (pointCount - 1)));
      const done = nextProgress >= 1;

      onStateChange({
        progress: nextProgress,
        currentIndex: nextIndex,
        isPlaying: !done,
      });

      if (!done) {
        rafId = window.requestAnimationFrame(tick);
      }
    };

    rafId = window.requestAnimationFrame(tick);
    return () => {
      window.cancelAnimationFrame(rafId);
    };
  }, [onStateChange, pointCount, state.isPlaying, state.progress, state.speed]);

  const progressPct = Math.round(clamp(state.progress, 0, 1) * 100);

  return (
    <section className="simulation-player">
      <div className="simulation-player__head">
        <div>
          <p className="panel__eyebrow">Simülasyon</p>
          <h3>Yol animasyonu</h3>
        </div>
        <strong data-testid="simulation-progress-label">%{progressPct}</strong>
      </div>

      <PlanCanvas
        pathPoints={points}
        walls={walls}
        progress={state.progress}
        showGrid
        testId="simulation-canvas"
      />

      <div className="simulation-player__controls">
        <button
          type="button"
          className="primary-button"
          onClick={() => onStateChange({ isPlaying: true })}
          disabled={pointCount < 2}
        >
          Oynat
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={() => onStateChange({ isPlaying: false })}
          disabled={!state.isPlaying}
        >
          Duraklat
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={() => onStateChange({ isPlaying: false, progress: 0, currentIndex: 0 })}
          disabled={pointCount < 2}
        >
          Sıfırla
        </button>
      </div>

      <div className="simulation-player__footer">
        <div className="simulation-player__speed" role="group" aria-label="Simülasyon hızı">
          {speedOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`secondary-button ${state.speed === option.value ? "simulation-player__speed--active" : ""}`}
              onClick={() => onStateChange({ speed: option.value })}
            >
              {option.label}
            </button>
          ))}
        </div>
        <progress
          data-testid="simulation-progress"
          className="simulation-player__progress"
          max={100}
          value={progressPct}
        />
      </div>
    </section>
  );
}

