#!/usr/bin/env python3
"""LayoutBot V3 demo DXF dosyalarını yeniden üretir (harici bağımlılık yok)."""

from __future__ import annotations

from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "public" / "demo"


def _header() -> str:
    return """0
SECTION
2
HEADER
9
$INSUNITS
70
4
0
ENDSEC
0
SECTION
2
ENTITIES
"""


def _line(x1: float, y1: float, x2: float, y2: float, layer: str = "WALLS") -> str:
    return f"""0
LINE
8
{layer}
10
{x1:g}
20
{y1:g}
11
{x2:g}
21
{y2:g}
"""


def _footer() -> str:
    return """0
ENDSEC
0
EOF
"""


def write_dxf(path: Path, segments: list[tuple[float, float, float, float]]) -> None:
    body = _header() + "".join(_line(*s) for s in segments) + _footer()
    path.write_text(body, encoding="ascii", newline="\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    write_dxf(
        OUT_DIR / "demo_square_room.dxf",
        [(0, 0, 5000, 0), (5000, 0, 5000, 4000), (5000, 4000, 0, 4000), (0, 4000, 0, 0)],
    )
    write_dxf(
        OUT_DIR / "demo_two_segments.dxf",
        [(0, 0, 2000, 0), (3000, 1000, 5000, 1000)],
    )
    write_dxf(
        OUT_DIR / "demo_room_door_gap.dxf",
        [
            (0, 0, 1500, 0),
            (3500, 0, 5000, 0),
            (5000, 0, 5000, 4000),
            (5000, 4000, 0, 4000),
            (0, 4000, 0, 0),
        ],
    )
    print(f"Wrote 3 demo DXF files to {OUT_DIR}")


if __name__ == "__main__":
    main()
