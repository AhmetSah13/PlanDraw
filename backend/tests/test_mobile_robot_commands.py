from __future__ import annotations

import math

from app.robot.mobile_robot_commands import (
    convert_path_to_mobile_robot_commands,
    get_preview_heading_deg,
)


def test_contiguous_segments_one_move_many_draw():
    """
    Komşu (uç uca) segmentler:
    - Başta SET_ORIGIN + SET_HEADING + PEN_UP olmalı.
    - İlk stroke için tek MOVE_TO, ardından birden çok DRAW_TO olmalı.
    - Sonda PEN_UP + END ile bitmeli.
    """
    segments = [
        (0.0, 0.0, 1.0, 0.0),
        (1.0, 0.0, 2.0, 0.0),
    ]
    res = convert_path_to_mobile_robot_commands(segments, start_heading_deg=0.0)
    cmds = res["commands"]

    assert cmds[0] == "SET_ORIGIN 0.000000 0.000000"
    assert cmds[1] == "SET_HEADING 0.000000"
    assert cmds[2] == "PEN_UP"
    assert cmds[3] == "MOVE_TO 0.000000 0.000000"
    assert cmds[4] == "PEN_DOWN"
    # İki DRAW_TO ardışık
    assert cmds[5] == "DRAW_TO 1.000000 0.000000"
    assert cmds[6] == "DRAW_TO 2.000000 0.000000"
    # Sonda PEN_UP + END
    assert cmds[-2] == "PEN_UP"
    assert cmds[-1] == "END"

    assert res["move_count"] == 3  # 1 MOVE_TO + 2 DRAW_TO
    assert res["travel_command_count"] == 1
    assert res["draw_command_count"] == 2
    assert math.isclose(res["drawn_length_m"], 2.0)
    assert math.isclose(res["travel_length_m"], 0.0)


def test_disconnected_segments_pen_up_and_move_to_between():
    """
    Bağlantısız segmentler:
    - İlk stroke: MOVE_TO + PEN_DOWN + DRAW_TO
    - İkinci stroke: önce PEN_UP, sonra MOVE_TO, sonra PEN_DOWN + DRAW_TO olmalı.
    """
    segments = [
        (0.0, 0.0, 1.0, 0.0),
        (2.0, 0.0, 3.0, 0.0),
    ]
    res = convert_path_to_mobile_robot_commands(segments, start_heading_deg=0.0)
    cmds = res["commands"]

    # Başlangıç
    assert cmds[0] == "SET_ORIGIN 0.000000 0.000000"
    assert cmds[1] == "SET_HEADING 0.000000"
    assert cmds[2] == "PEN_UP"
    assert cmds[3] == "MOVE_TO 0.000000 0.000000"
    assert cmds[4] == "PEN_DOWN"
    assert cmds[5] == "DRAW_TO 1.000000 0.000000"

    # İkinci stroke başlangıcında PEN_UP + MOVE_TO + PEN_DOWN olmalı
    assert "PEN_UP" in cmds[6]
    assert "MOVE_TO 2.000000 0.000000" in cmds[7]
    assert "PEN_DOWN" in cmds[8]
    assert "DRAW_TO 3.000000 0.000000" in cmds[9]

    # Sonda PEN_UP + END
    assert cmds[-2] == "PEN_UP"
    assert cmds[-1] == "END"

    # Metrikler
    assert res["move_count"] == 4  # 2 MOVE_TO + 2 DRAW_TO
    assert res["travel_command_count"] == 2
    assert res["draw_command_count"] == 2
    assert math.isclose(res["drawn_length_m"], 2.0)
    # Travel: 0→0 (0) + 1→2 (1) = 1
    assert math.isclose(res["travel_length_m"], 1.0)


def test_starts_with_init_and_ends_with_end():
    """
    Komut akışı her zaman:
      SET_ORIGIN, SET_HEADING, PEN_UP ... PEN_UP, END
    şeklinde başlamalı/bitmeli.
    """
    segments = [
        (1.0, 2.0, 3.0, 4.0),
    ]
    res = convert_path_to_mobile_robot_commands(segments, start_xy=(1.0, 2.0), start_heading_deg=45.0)
    cmds = res["commands"]

    assert cmds[0] == "SET_ORIGIN 1.000000 2.000000"
    assert cmds[1] == "SET_HEADING 45.000000"
    assert cmds[2] == "PEN_UP"
    assert cmds[-2] == "PEN_UP"
    assert cmds[-1] == "END"


def test_zero_length_and_duplicate_segments_sanitized():
    """
    Zero-length ve duplicate segmentler sanitize aşamasında atılmalı;
    metrikler ve komut sayıları sadece gerçek çizimi yansıtmalı.
    """
    segments = [
        (0.0, 0.0, 0.0, 0.0),  # zero-length
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),  # duplicate
    ]
    res = convert_path_to_mobile_robot_commands(segments, start_heading_deg=0.0)
    cmds = res["commands"]

    # Sadece tek stroke ve tek çizgi olmalı
    assert "MOVE_TO 0.000000 0.000000" in cmds
    assert cmds.count("DRAW_TO 1.000000 0.000000") == 1
    assert res["sanitized_segment_count"] == 1
    assert res["input_segment_count"] == 3
    assert math.isclose(res["drawn_length_m"], 1.0)


def test_heading_auto_compute_quadrants():
    """
    Otomatik heading:
      - sağa: 0°
      - yukarı: 90°
      - sola: 180° veya -180° (biz -180..180 normalliyoruz)
      - aşağı: -90°
    """
    # Sağ yön
    res_right = convert_path_to_mobile_robot_commands([(0.0, 0.0, 1.0, 0.0)])
    assert math.isclose(res_right["start_heading_deg"], 0.0)

    # Yukarı
    res_up = convert_path_to_mobile_robot_commands([(0.0, 0.0, 0.0, 1.0)])
    assert math.isclose(res_up["start_heading_deg"], 90.0)

    # Sola
    res_left = convert_path_to_mobile_robot_commands([(0.0, 0.0, -1.0, 0.0)])
    # -180 ile 180 arasında normalize edildiği için mutlak değeri 180 olmalı
    assert math.isclose(abs(res_left["start_heading_deg"]), 180.0)

    # Aşağı
    res_down = convert_path_to_mobile_robot_commands([(0.0, 0.0, 0.0, -1.0)])
    assert math.isclose(res_down["start_heading_deg"], -90.0)


def test_heading_matches_first_draw_to_vector():
    """
    İlk gerçek DRAW_TO vektörü ile SET_HEADING değeri birebir aynı olmalı.
    """
    segs = [
        (0.0, -0.5, 0.0, -1.5),  # Dikey aşağı (yaklaşık -90°)
        (1.0, 1.0, 2.0, 1.0),
    ]
    res = convert_path_to_mobile_robot_commands(
        segs, start_xy=(0.0, 0.0), start_heading_deg=None
    )
    cmds = res["commands"]

    # İlk DRAW_TO komutunu ve ona karşılık gelen başlangıç noktasını bul
    first_draw_idx = next(i for i, c in enumerate(cmds) if c.startswith("DRAW_TO "))
    # Başlangıç noktası, geriye doğru ilk MOVE_TO satırından gelir
    move_idx = next(
        i for i in range(first_draw_idx - 1, -1, -1) if cmds[i].startswith("MOVE_TO ")
    )

    _, sx_str, sy_str = cmds[move_idx].split()
    _, ex_str, ey_str = cmds[first_draw_idx].split()

    sx, sy = float(sx_str), float(sy_str)
    ex, ey = float(ex_str), float(ey_str)

    dx = ex - sx
    dy = ey - sy
    ang = math.degrees(math.atan2(dy, dx))
    if ang > 180.0:
        ang -= 360.0
    if ang <= -180.0:
        ang += 360.0

    assert math.isclose(ang, res["start_heading_deg"], abs_tol=1e-6)


def test_preview_heading_equals_command_heading():
    """
    Preview yön oku ile komut SET_HEADING tek kaynaktan gelmeli.
    get_preview_heading_deg, convert_path_to_mobile_robot_commands ile aynı değeri döner.
    """
    segs = [(0.0, -0.5, 0.0, -1.5), (1.0, 1.0, 2.0, 1.0)]
    mr = convert_path_to_mobile_robot_commands(segs, start_heading_deg=None)
    cmd_heading = mr["start_heading_deg"]
    preview_heading = get_preview_heading_deg(segs)
    assert math.isclose(cmd_heading, preview_heading, abs_tol=1e-6)


def test_empty_input_safe_output():
    """Boş input için güvenli ve tutarlı komut akışı dönmeli."""
    res = convert_path_to_mobile_robot_commands([])
    cmds = res["commands"]
    assert cmds[0].startswith("SET_ORIGIN")
    assert cmds[1].startswith("SET_HEADING")
    assert cmds[2] == "PEN_UP"
    assert cmds[-1] == "END"
    assert res["move_count"] == 0
    assert res["draw_command_count"] == 0
    assert res["travel_command_count"] == 0
    assert res["sanitized_segment_count"] == 0


def test_command_invariants():
    """
    Genel invariantler:
      - Başlangıç: SET_ORIGIN, SET_HEADING, PEN_UP
      - Hiçbir zaman PEN_DOWN sonrası MOVE_TO yok
      - DRAW_TO sadece PEN_DOWN iken geliyor
      - Sonda PEN_UP + END
    """
    segs = [
        (0.0, 0.0, 1.0, 0.0),
        (2.0, 0.0, 3.0, 0.0),
    ]
    res = convert_path_to_mobile_robot_commands(segs)
    cmds = res["commands"]

    assert cmds[0].startswith("SET_ORIGIN")
    assert cmds[1].startswith("SET_HEADING")
    assert cmds[2] == "PEN_UP"
    assert cmds[-2] == "PEN_UP"
    assert cmds[-1] == "END"

    pen_down = False
    for cmd in cmds[3:]:
        if cmd == "PEN_DOWN":
            pen_down = True
            continue
        if cmd == "PEN_UP":
            pen_down = False
            continue
        if cmd.startswith("MOVE_TO"):
            # MOVE_TO her zaman pen_up iken gelmeli
            assert not pen_down
        if cmd.startswith("DRAW_TO"):
            # DRAW_TO her zaman pen_down iken gelmeli
            assert pen_down

