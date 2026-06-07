import { describe, expect, it } from "vitest";
import {
  buildSimulationSegments,
  createIdlePlayback,
  parseCommandsToSegments,
  pathPointsToSegments,
  startPlayback,
  tickPlayback,
} from "./commandSimulation";

const SAMPLE = `BEGIN
PEN UP
MOVE 0 0
PEN DOWN
MOVE 100 0
MOVE 100 50
PEN UP
MOVE 200 50
PEN DOWN
MOVE 200 100
END`;

describe("commandSimulation", () => {
  it("komutlardan simülasyon segmentleri çıkarır", () => {
    const segs = parseCommandsToSegments(SAMPLE);
    expect(segs.length).toBeGreaterThanOrEqual(4);
    expect(segs.some((s) => s.kind === "draw")).toBe(true);
    expect(segs.some((s) => s.kind === "travel")).toBe(true);
  });

  it("PEN UP travel, PEN DOWN draw ayrımını doğru yapar", () => {
    const segs = parseCommandsToSegments(SAMPLE);
    const drawSeg = segs.find((s) => s.x2 === 100 && s.y2 === 0);
    const travelSeg = segs.find((s) => s.x2 === 200 && s.y2 === 50 && s.kind === "travel");
    expect(drawSeg?.kind).toBe("draw");
    expect(travelSeg?.kind).toBe("travel");
  });

  it("komut yoksa pathPoints yedek segment üretir", () => {
    const segs = buildSimulationSegments("", [
      [0, 0],
      [10, 0],
      [10, 10],
    ]);
    expect(segs).toHaveLength(2);
    expect(segs.every((s) => s.kind === "draw")).toBe(true);
  });

  it("simülasyon başlatınca progress sıfırlanır", () => {
    const segs = pathPointsToSegments([
      [0, 0],
      [50, 0],
    ]);
    const pb = startPlayback(1, segs);
    expect(pb.active).toBe(true);
    expect(pb.progress).toBe(0);
    expect(pb.completed).toBe(false);
  });

  it("tickPlayback ilerleme artırır ve tamamlar", () => {
    const segs = parseCommandsToSegments(SAMPLE);
    let pb = startPlayback(2, segs);
    for (let i = 0; i < 500; i++) {
      pb = tickPlayback(pb, segs, 16, 5000);
      if (pb.completed) break;
    }
    expect(pb.completed).toBe(true);
    expect(pb.progress).toBe(100);
  });

  it("createIdlePlayback yeni dosya reset durumunu temsil eder", () => {
    const idle = createIdlePlayback();
    expect(idle.active).toBe(false);
    expect(idle.progress).toBe(0);
    expect(idle.completed).toBe(false);
  });
});
