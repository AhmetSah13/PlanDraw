# test_normalized_plan.py — NormalizedPlan import (Milestone 1) + normalizer (Milestone 2)
from __future__ import annotations

import pytest
pytest.importorskip("pydantic")
pytest.importorskip("fastapi")
pytestmark = pytest.mark.integration

import unittest
import sys
from pathlib import Path

# backend/tests
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.normalization.normalized_plan import import_plan_from_json
from app.normalization.plan_normalizer import NormalizeOptions, normalize_plan
from pydantic import ValidationError
from app.api.main import import_plan
from app.api.schemas import NormalizedPlanIn


class TestImportPlanFromJson(unittest.TestCase):
    """import_plan_from_json birim testleri."""

    def test_valid_json_ok_and_version_v1(self):
        data = {
            "version": "v1",
            "units": "mm",
            "scale": 1.0,
            "origin": {"x": 0, "y": 0},
            "segments": [
                {"x1": 0, "y1": 0, "x2": 100, "y2": 0},
                {"x1": 100, "y1": 0, "x2": 100, "y2": 100},
            ],
        }
        plan = import_plan_from_json(data)
        self.assertEqual(plan.version, "v1")
        self.assertEqual(len(plan.segments), 2)
        self.assertEqual(plan.units, "mm")

    def test_valid_json_segments_count_matches(self):
        data = {
            "segments": [
                {"x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"x1": 10, "y1": 0, "x2": 10, "y2": 10},
                {"x1": 10, "y1": 10, "x2": 0, "y2": 10},
                {"x1": 0, "y1": 10, "x2": 0, "y2": 0},
            ],
        }
        plan = import_plan_from_json(data)
        self.assertEqual(len(plan.segments), 4)
        self.assertEqual(plan.segments[0].x1, 0)
        self.assertEqual(plan.segments[0].y2, 0)

    def test_empty_segments_fails(self):
        data = {"segments": []}
        with self.assertRaises(ValueError) as ctx:
            import_plan_from_json(data)
        self.assertIn("boş", str(ctx.exception).lower())

    def test_missing_segments_fails(self):
        data = {"version": "v1"}
        with self.assertRaises(ValueError) as ctx:
            import_plan_from_json(data)
        self.assertIn("segments", str(ctx.exception).lower())

    def test_invalid_units_fails(self):
        data = {
            "units": "inch",
            "segments": [{"x1": 0, "y1": 0, "x2": 1, "y2": 0}],
        }
        with self.assertRaises(ValueError) as ctx:
            import_plan_from_json(data)
        self.assertIn("units", str(ctx.exception).lower())

    def test_missing_segment_fields_fails(self):
        data = {"segments": [{"x1": 0, "y1": 0}]}  # x2, y2 eksik
        with self.assertRaises(ValidationError):
            import_plan_from_json(data)


class TestImportPlanAPI(unittest.TestCase):
    """POST /api/import_plan handler testi (handler doğrudan çağrılıyor, TestClient/httpx yok)."""

    def test_api_valid_json_returns_ok_true_and_normalized(self):
        req = NormalizedPlanIn(
            version="v1",
            units="mm",
            segments=[
                {"x1": 0, "y1": 0, "x2": 50, "y2": 0},
                {"x1": 50, "y1": 0, "x2": 50, "y2": 50},
            ],
        )
        resp = import_plan(req)
        self.assertTrue(resp.ok)
        self.assertIsNone(resp.error)
        self.assertIsNotNone(resp.normalized)
        self.assertEqual(resp.normalized["version"], "v1")
        self.assertEqual(len(resp.normalized["segments"]), 2)
        self.assertEqual(resp.warnings, [])

    def test_api_empty_segments_returns_ok_false(self):
        req = NormalizedPlanIn(segments=[])
        resp = import_plan(req)
        self.assertFalse(resp.ok)
        self.assertIsNotNone(resp.error)
        self.assertIn("segments", resp.error.lower())

    def test_api_missing_segments_returns_ok_false(self):
        req = NormalizedPlanIn(version="v1")  # segments default []
        resp = import_plan(req)
        self.assertFalse(resp.ok)
        self.assertIsNotNone(resp.error)


class TestNormalizerMilestone2(unittest.TestCase):
    """Normalizasyon (Milestone 2): collinear merge, idempotency, zero-length drop."""

    def test_collinear_merge_two_segments_into_one_via_api(self):
        # (0,0)-(10,0) ve (10,0)-(20,0) -> normalize=true -> tek segment (0,0)-(20,0)
        req = NormalizedPlanIn(
            segments=[
                {"x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"x1": 10, "y1": 0, "x2": 20, "y2": 0},
            ],
            normalize=True,
        )
        resp = import_plan(req)
        self.assertTrue(resp.ok, resp.error)
        self.assertEqual(len(resp.normalized["segments"]), 1)
        seg = resp.normalized["segments"][0]
        self.assertEqual(seg["x1"], 0)
        self.assertEqual(seg["y1"], 0)
        self.assertEqual(seg["x2"], 20)
        self.assertEqual(seg["y2"], 0)

    def test_normalize_twice_idempotent_same_segments(self):
        # İki kollinear segment birleşir; tekrar normalize aynı listeyi vermeli
        plan = import_plan_from_json({
            "segments": [
                {"x1": 0, "y1": 0, "x2": 5, "y2": 0},
                {"x1": 5, "y1": 0, "x2": 10, "y2": 0},
            ],
        })
        opts = NormalizeOptions()
        p1, _ = normalize_plan(plan, opts)
        p2, _ = normalize_plan(p1, opts)
        self.assertEqual(len(p1.segments), 1)
        self.assertEqual(len(p2.segments), 1)
        self.assertEqual(p1.segments[0].x1, p2.segments[0].x1)
        self.assertEqual(p1.segments[0].y1, p2.segments[0].y1)
        self.assertEqual(p1.segments[0].x2, p2.segments[0].x2)
        self.assertEqual(p1.segments[0].y2, p2.segments[0].y2)

    def test_zero_length_dropped_warnings_contain_dropped(self):
        # Bir sıfır-uzunluk segment atılır; kalan iki segment kollinear olduğu için birleşir -> 1 segment
        req = NormalizedPlanIn(
            segments=[
                {"x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"x1": 1, "y1": 1, "x2": 1, "y2": 1},  # sıfır uzunluk
                {"x1": 10, "y1": 0, "x2": 20, "y2": 0},
            ],
            normalize=True,
        )
        resp = import_plan(req)
        self.assertTrue(resp.ok, resp.error)
        self.assertGreaterEqual(len(resp.normalized["segments"]), 1)
        self.assertTrue(
            any("Dropped" in w for w in resp.warnings),
            f"warnings should contain 'Dropped': {resp.warnings}",
        )

    def test_min_segment_len_drops_short_segments_and_warns(self):
        # 1 uzun + 2 çok kısa segment; min_segment_len ile kısalar düşer
        from app.normalization.normalized_plan import NormalizedPlan, SegmentIn, OriginIn

        plan = NormalizedPlan(
            version="v1",
            units="mm",
            scale=1.0,
            origin=OriginIn(x=0.0, y=0.0),
            segments=[
                SegmentIn(x1=0.0, y1=0.0, x2=100.0, y2=0.0),   # uzun
                SegmentIn(x1=0.0, y1=0.0, x2=0.1, y2=0.0),     # kısa
                SegmentIn(x1=0.0, y1=0.0, x2=0.05, y2=0.0),    # daha kısa
            ],
        )
        opts = NormalizeOptions(min_segment_len=1.0, merge_collinear=False, drop_zero_length=False)
        out, warnings = normalize_plan(plan, opts)
        self.assertEqual(len(out.segments), 1)
        self.assertTrue(
            any("Dropped 2" in w for w in warnings),
            f"warnings should mention Dropped 2: {warnings}",
        )

    def test_segment_budget_keep_longest(self):
        # 5 segment, farklı uzunluklar; budget=2 -> en uzun 2'yi, orijinal relative order ile tutmalı
        from app.normalization.normalized_plan import NormalizedPlan, SegmentIn, OriginIn

        segs = [
            SegmentIn(x1=0.0, y1=0.0, x2=1.0, y2=0.0),   # len 1
            SegmentIn(x1=0.0, y1=0.0, x2=5.0, y2=0.0),   # len 5
            SegmentIn(x1=0.0, y1=0.0, x2=3.0, y2=0.0),   # len 3
            SegmentIn(x1=0.0, y1=0.0, x2=2.0, y2=0.0),   # len 2
            SegmentIn(x1=0.0, y1=0.0, x2=4.0, y2=0.0),   # len 4
        ]
        plan = NormalizedPlan(
            version="v1",
            units="mm",
            scale=1.0,
            origin=OriginIn(x=0.0, y=0.0),
            segments=segs,
        )
        opts = NormalizeOptions(
            merge_collinear=False,
            drop_zero_length=False,
            segment_budget=2,
            budget_strategy="keep_longest",
        )
        out, warnings = normalize_plan(plan, opts)
        self.assertEqual(len(out.segments), 2)
        # En uzun iki: len 5 (index 1), len 4 (index 4) -> orijinal sıraya göre [1,4]
        self.assertAlmostEqual(out.segments[0].x2, 5.0)
        self.assertAlmostEqual(out.segments[1].x2, 4.0)
        self.assertTrue(
            any("Segment budget applied" in w for w in warnings),
            f"warnings should contain budget message: {warnings}",
        )

    def test_segment_budget_error(self):
        from app.normalization.normalized_plan import NormalizedPlan, SegmentIn, OriginIn

        plan = NormalizedPlan(
            version="v1",
            units="mm",
            scale=1.0,
            origin=OriginIn(x=0.0, y=0.0),
            segments=[
                SegmentIn(x1=0.0, y1=0.0, x2=1.0, y2=0.0),
                SegmentIn(x1=0.0, y1=0.0, x2=2.0, y2=0.0),
                SegmentIn(x1=0.0, y1=0.0, x2=3.0, y2=0.0),
            ],
        )
        opts = NormalizeOptions(
            merge_collinear=False,
            drop_zero_length=False,
            segment_budget=2,
            budget_strategy="error",
        )
        with self.assertRaises(ValueError) as ctx:
            normalize_plan(plan, opts)
        self.assertIn("Plan çok detaylı", str(ctx.exception))

    def test_recenter_center_moves_bbox_center_near_zero(self):
        from app.normalization.normalized_plan import NormalizedPlan, SegmentIn, OriginIn

        plan = NormalizedPlan(
            version="v1",
            units="mm",
            scale=1.0,
            origin=OriginIn(x=0.0, y=0.0),
            segments=[
                SegmentIn(x1=100.0, y1=200.0, x2=200.0, y2=200.0),
                SegmentIn(x1=200.0, y1=200.0, x2=200.0, y2=300.0),
            ],
        )
        opts = NormalizeOptions(
            merge_collinear=False,
            drop_zero_length=False,
            recenter=True,
            recenter_mode="center",
        )
        out, warnings = normalize_plan(plan, opts)
        xs = [seg.x1 for seg in out.segments] + [seg.x2 for seg in out.segments]
        ys = [seg.y1 for seg in out.segments] + [seg.y2 for seg in out.segments]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0
        self.assertAlmostEqual(cx, 0.0, places=6)
        self.assertAlmostEqual(cy, 0.0, places=6)
        self.assertTrue(
            any("Recentering applied" in w for w in warnings),
            f"warnings should contain recenter message: {warnings}",
        )


class TestImportPlanMilestone3(unittest.TestCase):
    """Import plan plan_text / commands_text / walls (Milestone 3)."""

    def test_import_plan_returns_plan_text_and_commands_text(self):
        # Kare oda: 4 segment
        req = NormalizedPlanIn(
            segments=[
                {"x1": 0, "y1": 0, "x2": 200, "y2": 0},
                {"x1": 200, "y1": 0, "x2": 200, "y2": 200},
                {"x1": 200, "y1": 200, "x2": 0, "y2": 200},
                {"x1": 0, "y1": 200, "x2": 0, "y2": 0},
            ],
            normalize=True,
            return_plan_text=True,
            return_commands_text=True,
        )
        resp = import_plan(req)
        self.assertTrue(resp.ok, resp.error)
        self.assertIsNotNone(resp.plan_text)
        line_count = sum(1 for s in resp.plan_text.strip().splitlines() if s.strip().startswith("LINE "))
        self.assertEqual(line_count, 4, f"plan_text should contain 4 LINE lines: {resp.plan_text!r}")
        self.assertIsNotNone(resp.commands_text)
        self.assertIn("PEN", resp.commands_text)
        self.assertTrue(
            "MOVE" in resp.commands_text or "FORWARD" in resp.commands_text,
            f"commands_text should contain movement: {resp.commands_text[:500]!r}",
        )
        self.assertIsNotNone(resp.walls)
        self.assertEqual(len(resp.walls), 4)

    def test_import_plan_plan_text_compiles_to_same_commands_via_compile_plan(self):
        # import_plan döndürdüğü plan_text'i compile_plan'a verince aynı commands_text elde edilmeli
        from app.api.main import compile_plan
        from app.api.schemas import CompilePlanRequest

        req = NormalizedPlanIn(
            segments=[
                {"x1": 0, "y1": 0, "x2": 100, "y2": 0},
                {"x1": 100, "y1": 0, "x2": 100, "y2": 100},
                {"x1": 100, "y1": 100, "x2": 0, "y2": 100},
                {"x1": 0, "y1": 100, "x2": 0, "y2": 0},
            ],
            return_plan_text=True,
            return_commands_text=True,
            step_size=5.0,
            speed=120.0,
        )
        resp = import_plan(req)
        self.assertTrue(resp.ok, resp.error)
        self.assertIsNotNone(resp.plan_text)
        self.assertIsNotNone(resp.commands_text)

        compile_req = CompilePlanRequest(
            plan_text=resp.plan_text,
            step_size=5.0,
            speed=120.0,
            world_scale=1.0,
            world_offset=(0.0, 0.0),
        )
        compile_resp = compile_plan(compile_req)
        self.assertTrue(compile_resp.get("ok"), compile_resp)
        compiled_text = compile_resp.get("commands_text") or compile_resp.get("commands_text_raw", "")
        self.assertEqual(resp.commands_text, compiled_text)


class TestCompilePlanEmptyPath(unittest.TestCase):
    """compile_plan boş plan veya çizilebilir nokta üretmeyen plan için ok=False döner."""

    def test_empty_plan_text_returns_ok_false(self):
        from app.api.main import compile_plan
        from app.api.schemas import CompilePlanRequest

        req = CompilePlanRequest(
            plan_text="# boş plan\n",
            step_size=5.0,
            speed=120.0,
            world_scale=1.0,
            world_offset=(0.0, 0.0),
        )
        resp = compile_plan(req)
        self.assertFalse(resp.get("ok"), resp)
        self.assertIn("çizilebilir nokta üretmedi", resp.get("error", ""))
