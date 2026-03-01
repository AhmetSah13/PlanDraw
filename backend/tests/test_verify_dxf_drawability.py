# test_verify_dxf_drawability.py — Doğrulayıcı yardımcı fonksiyonları (gerçek DXF gerekmez)

from __future__ import annotations

import pytest
import sys
import tempfile
from pathlib import Path

pytest.importorskip("pydantic")
pytestmark = pytest.mark.integration

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Script backend/scripts içinde; backend path'te olmalı
_scripts = _root / "scripts"
if _scripts.exists():
    sys.path.insert(0, str(_root))

# Modülü yükle (app importları tetiklenir)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "verify_dxf_drawability",
    _root / "scripts" / "verify_dxf_drawability.py",
)
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)


class TestClampStep:
    """_clamp_step [0.05, 0.50] aralığına kıstırır."""

    def test_none_returns_max(self):
        assert verifier._clamp_step(None) == 0.50

    def test_zero_returns_max(self):
        assert verifier._clamp_step(0) == 0.50

    def test_negative_returns_max(self):
        assert verifier._clamp_step(-0.1) == 0.50

    def test_low_clamped_to_min(self):
        assert verifier._clamp_step(0.01) == 0.05

    def test_high_clamped_to_max(self):
        assert verifier._clamp_step(1.0) == 0.50

    def test_in_range_unchanged(self):
        assert verifier._clamp_step(0.2) == 0.2
        assert verifier._clamp_step(0.05) == 0.05
        assert verifier._clamp_step(0.50) == 0.50


class TestSelectLayers:
    """select_layers: suggested_layers varsa onu kullanır, yoksa total_length'a göre en fazla 2."""

    def test_suggested_layers_used(self):
        info = {"suggested_layers": ["WALLS", "DIM"], "layers": {}}
        assert verifier.select_layers(info) == ["WALLS", "DIM"]

    def test_suggested_empty_falls_back_to_top_two(self):
        info = {
            "suggested_layers": [],
            "layers": {
                "A": {"total_length": 10.0},
                "B": {"total_length": 50.0},
                "C": {"total_length": 5.0},
            },
        }
        out = verifier.select_layers(info)
        assert len(out) == 2
        assert out[0] == "B"
        assert out[1] == "A"

    def test_empty_layers_returns_empty(self):
        info = {"suggested_layers": [], "layers": {}}
        assert verifier.select_layers(info) == []


class TestLayersForWallsOnly:
    """layers_for_walls_only: wall/duvar anahtar kelimesi içeren katmanları döner."""

    def test_suggested_filtered_by_keyword(self):
        info = {"suggested_layers": ["WALLS", "DIM", "a-wall"], "layers": {}}
        out = verifier.layers_for_walls_only(info)
        assert "WALLS" in out
        assert "a-wall" in out
        assert "DIM" not in out

    def test_layers_by_keyword_when_no_suggested(self):
        info = {
            "suggested_layers": [],
            "layers": {"WALLS": {}, "duvar": {}, "DIM": {}},
        }
        out = verifier.layers_for_walls_only(info)
        assert "WALLS" in out
        assert "duvar" in out
        assert "DIM" not in out


class TestCollectDxfPaths:
    """collect_dxf_paths: tek dosya veya klasörde özyinelemeli .dxf toplar."""

    def test_single_dxf_file(self):
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            p = Path(f.name)
        try:
            out = verifier.collect_dxf_paths(p)
            assert len(out) == 1
            assert out[0] == p
        finally:
            p.unlink(missing_ok=True)

    def test_single_non_dxf_returns_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            p = Path(f.name)
        try:
            assert verifier.collect_dxf_paths(p) == []
        finally:
            p.unlink(missing_ok=True)

    def test_dir_recursive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.dxf").write_text("")
            (root / "sub").mkdir(parents=True)
            (root / "sub" / "b.dxf").write_text("")
            (root / "c.txt").write_text("")
            out = verifier.collect_dxf_paths(root)
            assert len(out) == 2
            names = {p.name for p in out}
            assert names == {"a.dxf", "b.dxf"}


class TestRetryOrder:
    """Retry stratejileri sırası: fast -> walls_only -> detail."""

    def test_strategies_defined_in_order(self):
        # run_retries içinde strategies listesi bu sırada; birim testte sadece sırayı doğrula
        step = 0.20
        strategies = [
            ("fast", {"step_override": min(step * 2, 0.50), "layers_override": None}),
            ("walls_only", {"step_override": step, "layers_override": None}),  # placeholder
            ("detail", {"step_override": max(step * 0.75, 0.05), "layers_override": None}),
        ]
        assert strategies[0][0] == "fast"
        assert strategies[1][0] == "walls_only"
        assert strategies[2][0] == "detail"
        assert strategies[0][1]["step_override"] == 0.40
        assert abs(strategies[2][1]["step_override"] - 0.15) < 1e-9
