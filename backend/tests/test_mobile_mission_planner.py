from __future__ import annotations

import math

from app.robot.mobile_mission_planner import plan_mobile_mission


def _p(*pts):
    return [tuple(map(float, p)) for p in pts]


def test_single_path_remains_same():
    paths = [_p((0.0, 0.0), (1.0, 0.0))]
    res = plan_mobile_mission(paths, start_xy=(0.0, 0.0), start_heading_deg=0.0)
    planned = res["planned_paths"]
    assert len(planned) == 1
    assert planned[0] == paths[0]


def test_two_paths_closer_first_selected():
    # İki ayrık path: (0,0)->(1,0) ve (10,0)->(11,0)
    p1 = _p((0.0, 0.0), (1.0, 0.0))
    p2 = _p((10.0, 0.0), (11.0, 0.0))
    paths = [p2, p1]  # sıralamayı ters veriyoruz
    res = plan_mobile_mission(
        paths,
        start_xy=(0.0, 0.0),
        start_heading_deg=0.0,
        planner_mode="travel_first",
    )
    planned = res["planned_paths"]
    # Başlangıca daha yakın olan p1 önce seçilmeli
    assert planned[0] == p1
    assert planned[1] == p2 or planned[1] == list(reversed(p2))


def test_reverse_direction_if_cheaper():
    # Robot (9,0) ve heading 0° iken:
    # p1 forward: start (5,0) → travel 4 m
    # p1 reverse: start (10,0) → travel 1 m
    # turn_weight=0 iken reverse yön daha ucuz olmalı (sadece travel mesafesi önemli).
    p1 = _p((5.0, 0.0), (10.0, 0.0))
    paths = [p1]
    res = plan_mobile_mission(
        paths,
        start_xy=(9.0, 0.0),
        start_heading_deg=0.0,
        optimize_order=True,
        optimize_direction=True,
        travel_weight=1.0,
        turn_weight=0.0,
    )
    planned = res["planned_paths"]
    # Başlangıç heading 180°, bu path sağa doğru; reverse edilirse sola doğru olur ve turn maliyeti düşer.
    assert planned[0] == list(reversed(p1))


def test_heading_influences_choice():
    # İki path: biri sağa, biri sola; travel uzaklıkları aynı (1 m),
    # travel_first modda tie-break ile heading uyumlu olan seçilir.
    right = _p((1.0, 0.0), (2.0, 0.0))  # sağa
    left = _p((-1.0, 0.0), (-2.0, 0.0))  # sola
    res = plan_mobile_mission(
        [right, left],
        start_xy=(0.0, 0.0),
        start_heading_deg=180.0,
        optimize_order=True,
        optimize_direction=False,
        planner_mode="travel_first",
    )
    planned = res["planned_paths"]
    # Travel aynı; heading tie-break ile sola (180° uyumlu) seçilmeli
    assert planned[0] == left


def test_weighted_mode_preserves_old_behavior():
    # weighted modda cost = travel_weight * travel + turn_weight * heading
    # turn_weight baskın: heading uyumlu path önce
    right = _p((1.0, 0.0), (2.0, 0.0))
    left = _p((-1.0, 0.0), (-2.0, 0.0))
    res = plan_mobile_mission(
        [right, left],
        start_xy=(0.0, 0.0),
        start_heading_deg=180.0,
        optimize_order=True,
        optimize_direction=False,
        planner_mode="weighted",
        travel_weight=0.1,
        turn_weight=1.0,
    )
    planned = res["planned_paths"]
    assert planned[0] == left


def test_optimize_order_false_preserves_order():
    p1 = _p((0.0, 0.0), (1.0, 0.0))
    p2 = _p((10.0, 0.0), (11.0, 0.0))
    paths = [p2, p1]
    res = plan_mobile_mission(
        paths,
        start_xy=(0.0, 0.0),
        start_heading_deg=0.0,
        optimize_order=False,
        optimize_direction=True,
    )
    planned = res["planned_paths"]
    # Sıra korunmalı
    assert len(planned) == 2
    assert planned[0][0] == p2[0] or planned[0][0] == p2[-1]
    assert planned[1][0] == p1[0] or planned[1][0] == p1[-1]


def test_optimize_direction_false_preserves_direction():
    p1 = _p((0.0, 0.0), (1.0, 0.0))
    p2 = _p((10.0, 0.0), (11.0, 0.0))
    paths = [p1, p2]
    res = plan_mobile_mission(
        paths,
        start_xy=(0.0, 0.0),
        start_heading_deg=0.0,
        optimize_order=True,
        optimize_direction=False,
    )
    planned = res["planned_paths"]
    assert planned[0] in (p1, p2)
    assert planned[0] != list(reversed(planned[0]))
    assert planned[1] in (p1, p2)
    assert planned[1] != list(reversed(planned[1]))


def test_empty_input_safe():
    res = plan_mobile_mission([], start_xy=(1.0, 2.0), start_heading_deg=45.0)
    assert res["planned_paths"] == []
    assert res["original_path_count"] == 0
    assert res["planned_path_count"] == 0
    assert math.isclose(res["total_travel_m"], 0.0)
    assert math.isclose(res["estimated_turn_deg"], 0.0)


def test_counts_and_geometry_preserved():
    p1 = _p((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))
    p2 = _p((5.0, 0.0), (6.0, 0.0))
    paths = [p1, p2]
    res = plan_mobile_mission(
        paths,
        start_xy=(0.0, 0.0),
        start_heading_deg=0.0,
        optimize_order=True,
        optimize_direction=True,
    )
    planned = res["planned_paths"]
    assert res["original_path_count"] == 2
    assert res["planned_path_count"] == 2
    # Planner path kaybetmemeli; sadece sıra/yön değiştirebilir
    assert sorted(len(p) for p in planned) == sorted(len(p) for p in paths)


def test_travel_tie_break_uses_heading():
    # İki path: (1,0)->(2,0) ve (-1,0)->(-2,0), başlangıç (0,0)
    # Travel mesafeleri aynı (1 m); heading 180° iken sola giden daha az turn
    p_right = _p((1.0, 0.0), (2.0, 0.0))
    p_left = _p((-1.0, 0.0), (-2.0, 0.0))
    res = plan_mobile_mission(
        [p_right, p_left],
        start_xy=(0.0, 0.0),
        start_heading_deg=180.0,
        optimize_order=True,
        optimize_direction=False,
        planner_mode="travel_first",
        travel_tie_band_ratio=0.05,
    )
    planned = res["planned_paths"]
    assert planned[0] == p_left


def test_degradation_guard_fallback():
    # degradation_limit=0.001 ile neredeyse her zaman fallback
    # (optimized > naive * 0.001, normal planlarda sağlanır)
    p1 = _p((0.0, 0.0), (1.0, 0.0))
    p2 = _p((5.0, 0.0), (6.0, 0.0))
    paths = [p1, p2]
    res = plan_mobile_mission(
        paths,
        start_xy=(0.0, 0.0),
        start_heading_deg=0.0,
        optimize_order=True,
        optimize_direction=True,
        planner_mode="travel_first",
        degradation_limit=0.001,
    )
    assert res["fallback_used"] is True
    assert res["planned_paths"] == [list(p1), list(p2)]


def test_fallback_planned_paths_equal_naive():
    p1 = _p((0.0, 0.0), (1.0, 0.0))
    p2 = _p((2.0, 0.0), (3.0, 0.0))
    paths = [p1, p2]
    res = plan_mobile_mission(
        paths,
        start_xy=(0.0, 0.0),
        start_heading_deg=0.0,
        degradation_limit=0.001,
    )
    assert res["fallback_used"] is True
    naive_plan = [list(p) for p in paths]
    assert res["planned_paths"] == naive_plan
