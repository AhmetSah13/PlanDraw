from __future__ import annotations

import math

from app.robot.command_generator import convert_path_to_robot_commands


def test_contiguous_segments_no_extra_pen_up():
    """
    Komşu (uç uca) segmentler:
    - İlk segmentten önce PEN_UP + MOVE + PEN_DOWN olmalı.
    - İki segment arasında ekstra PEN_UP olmamalı.
    - Son komut PEN_UP ile bitmeli.
    """
    segments = [
        (0.0, 0.0, 1.0, 0.0),
        (1.0, 0.0, 2.0, 0.0),
    ]
    res = convert_path_to_robot_commands(segments)
    cmds = res["commands"]

    # Başlangıç
    assert cmds[0] == "PEN_UP"
    assert cmds[1] == "MOVE 0.000000 0.000000"
    assert cmds[2] == "PEN_DOWN"
    # İki DRAW ardışık ve arada PEN_UP yok
    assert cmds[3] == "DRAW 1.000000 0.000000"
    assert cmds[4] == "DRAW 2.000000 0.000000"
    # Sonda PEN_UP
    assert cmds[-1] == "PEN_UP"

    # Metrikler (absolute)
    assert res["move_count"] == 3  # 1 MOVE + 2 DRAW
    assert math.isclose(res["drawn_length_m"], 2.0)
    assert math.isclose(res["travel_length_m"], 0.0)


def test_disconnected_segments_pen_up_between():
    """
    Bağlantısız segmentler:
    - İlk segmentten önce PEN_UP + MOVE + PEN_DOWN.
    - İkinci segmentten önce PEN_UP + MOVE + PEN_DOWN gelmeli.
    - Son komut PEN_UP olmalı.
    """
    segments = [
        (0.0, 0.0, 1.0, 0.0),
        (2.0, 0.0, 3.0, 0.0),
    ]
    res = convert_path_to_robot_commands(segments)
    cmds = res["commands"]

    # İlk stroke
    assert cmds[0] == "PEN_UP"
    assert cmds[1] == "MOVE 0.000000 0.000000"
    assert cmds[2] == "PEN_DOWN"
    assert cmds[3] == "DRAW 1.000000 0.000000"

    # İkinci stroke'tan önce PEN_UP + MOVE + PEN_DOWN olmalı
    # Örnek dizi: [PEN_UP, MOVE 0, PEN_DOWN, DRAW 1, PEN_UP, MOVE 2, PEN_DOWN, DRAW 3, PEN_UP]
    assert "PEN_UP" in cmds[4]
    assert "MOVE 2.000000 0.000000" in cmds[5]
    assert "PEN_DOWN" in cmds[6]
    assert "DRAW 3.000000 0.000000" in cmds[7]

    # Sonda PEN_UP
    assert cmds[-1] == "PEN_UP"

    # Metrikler
    # Çizim: 1 birim + 1 birim = 2.0
    # Travel: 0→0 (0) + 1→2 (1) = 1.0
    assert res["move_count"] == 4  # 2 MOVE + 2 DRAW
    assert math.isclose(res["drawn_length_m"], 2.0)
    assert math.isclose(res["travel_length_m"], 1.0)

