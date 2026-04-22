from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

try:
    import ezdxf
    from ezdxf.entities import DXFGraphic, Insert
except Exception:  # pragma: no cover
    ezdxf = None  # type: ignore
    DXFGraphic = object  # type: ignore
    Insert = object  # type: ignore


@dataclass(frozen=True)
class ExplodeConfig:
    max_recursion_depth: int = 8
    explode_inserts: bool = True


def explode_inserts(
    entities: Iterable["DXFGraphic"],
    *,
    cfg: ExplodeConfig,
) -> Tuple[List["DXFGraphic"], List[Dict[str, Any]]]:
    """
    INSERT patlatır (ezdxf virtual_entities). Dönüş: (flatten_entities, warnings).
    """
    out: List["DXFGraphic"] = []
    warnings: List[Dict[str, Any]] = []

    def _recurse(e: "DXFGraphic", depth: int) -> None:
        if not cfg.explode_inserts:
            out.append(e)
            return

        t = getattr(e, "dxftype", lambda: "")()
        if t != "INSERT":
            out.append(e)
            return

        if depth >= cfg.max_recursion_depth:
            layer = getattr(getattr(e, "dxf", None), "layer", "0") or "0"
            warnings.append(
                {
                    "code": "INSERT_TOO_DEEP",
                    "severity": "WARN",
                    "type": "INSERT",
                    "layer": layer,
                    "message": f"INSERT recursion limit: {cfg.max_recursion_depth}",
                    "user_action": "Blokları CAD'de patlatıp tekrar deneyin.",
                }
            )
            return

        ins: "Insert" = e  # type: ignore
        layer = getattr(getattr(ins, "dxf", None), "layer", "0") or "0"

        sx = float(getattr(getattr(ins, "dxf", None), "xscale", 1.0) or 1.0)
        sy = float(getattr(getattr(ins, "dxf", None), "yscale", 1.0) or 1.0)
        if abs(sx - sy) > 1e-9:
            warnings.append(
                {
                    "code": "NONUNIFORM_SCALE",
                    "severity": "WARN",
                    "type": "INSERT",
                    "layer": layer,
                    "message": f"Non-uniform scale: x={sx}, y={sy}",
                    "user_action": "Gerekirse CAD'de uniform scale ile yeniden kaydedin.",
                }
            )

        try:
            exploded_any = False
            for child in ins.virtual_entities():  # type: ignore[attr-defined]
                exploded_any = True
                _recurse(child, depth + 1)
            if exploded_any:
                warnings.append(
                    {
                        "code": "INSERT_EXPLODED",
                        "severity": "WARN",
                        "type": "INSERT",
                        "layer": layer,
                        "message": "INSERT patlatıldı (virtual_entities).",
                        "user_action": "Gerekirse sadece duvar katmanını seçin.",
                    }
                )
        except Exception as ex:
            warnings.append(
                {
                    "code": "INSERT_EXPLODE_FAIL",
                    "severity": "WARN",
                    "type": "INSERT",
                    "layer": layer,
                    "message": f"virtual_entities hatası: {ex!s}",
                    "user_action": "Blokları CAD'de patlatıp tekrar deneyin.",
                }
            )

    for e in entities:
        _recurse(e, 0)

    return out, warnings

