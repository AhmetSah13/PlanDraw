from __future__ import annotations

import math
from typing import Sequence

from app.alignment.alignment_model import (
    AlignedLayout,
    AlignmentReport,
    ControlPoint,
    RigidTransform2D,
)
from app.layout_ir.ir_types import LineObject, PolylineObject, PrintableLayout


def _weights(cps: Sequence[ControlPoint]) -> list[float]:
    out: list[float] = []
    for cp in cps:
        w = cp.weight
        if w is None:
            out.append(1.0)
        else:
            out.append(float(w))
    return out


def _centroid2(
    pts: Sequence[tuple[float, float]], weights: Sequence[float]
) -> tuple[float, float, float]:
    sw = sum(weights)
    if sw <= 0.0:
        return (0.0, 0.0, 0.0)
    sx = sum(weights[i] * pts[i][0] for i in range(len(pts)))
    sy = sum(weights[i] * pts[i][1] for i in range(len(pts)))
    return (sx / sw, sy / sw, sw)


def _mat_mul(
    a: tuple[tuple[float, float], tuple[float, float]],
    b: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    return (
        (
            a[0][0] * b[0][0] + a[0][1] * b[1][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1],
        ),
        (
            a[1][0] * b[0][0] + a[1][1] * b[1][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1],
        ),
    )


def _mat_det(m: tuple[tuple[float, float], tuple[float, float]]) -> float:
    return m[0][0] * m[1][1] - m[0][1] * m[1][0]


def _svd_2x2(
    m: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[
    tuple[tuple[float, float], tuple[float, float]],
    tuple[float, float],
    tuple[tuple[float, float], tuple[float, float]],
]:
    """
    2x2 gerçek M için SVD: M = U @ diag(s1,s2) @ Vt.
    Basit ve deterministik; küçük tekil değerlerde sayısal sınırlar.
    """
    a, b = m[0][0], m[0][1]
    c, d = m[1][0], m[1][1]
    # B = M^T M (simetrik)
    p = a * a + c * c
    q = a * b + c * d
    r = b * b + d * d
    tr = p + r
    disc = (0.5 * (p - r)) ** 2 + q * q
    if disc < 0.0:
        disc = 0.0
    root = math.sqrt(disc)
    l1 = 0.5 * tr + root
    l2 = 0.5 * tr - root
    if l1 < 0.0:
        l1 = 0.0
    if l2 < 0.0:
        l2 = 0.0
    if l2 > l1:
        l1, l2 = l2, l1

    # Özvektörler (M^T M için)
    def eigenvector(lam: float) -> tuple[float, float]:
        if abs(q) > 1e-18:
            x, y = q, lam - p
        else:
            if abs(lam - p) <= abs(lam - r):
                x, y = 1.0, 0.0
            else:
                x, y = 0.0, 1.0
        n = math.hypot(x, y)
        if n <= 1e-18:
            return (1.0, 0.0)
        return (x / n, y / n)

    v1x, v1y = eigenvector(l1)
    v2x, v2y = -v1y, v1x
    # V = [v1 | v2], V^T satırları v1^T ve v2^T
    vt = ((v1x, v1y), (v2x, v2y))
    s1 = math.sqrt(l1)
    s2 = math.sqrt(l2)

    # U = M V S^{-1}
    def col_mv(col: tuple[float, float]) -> tuple[float, float]:
        return (a * col[0] + b * col[1], c * col[0] + d * col[1])

    def scale_inv(s: float) -> float:
        if s <= 1e-15:
            return 0.0
        return 1.0 / s

    u1 = col_mv((v1x, v1y))
    u2 = col_mv((v2x, v2y))
    si1 = scale_inv(s1)
    si2 = scale_inv(s2)
    u1 = (u1[0] * si1, u1[1] * si1)
    u2 = (u2[0] * si2, u2[1] * si2)
    u = ((u1[0], u2[0]), (u1[1], u2[1]))
    return u, (s1, s2), vt


def _fix_reflection(
    m: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Kabsch: R = U V^T; yansıtma varsa U'nun ikinci sütununu ters işaretle."""
    u, _s, vt = _svd_2x2(m)
    r = _mat_mul(u, vt)
    if _mat_det(r) >= 0.0:
        return r
    u_flip = ((u[0][0], -u[0][1]), (u[1][0], -u[1][1]))
    return _mat_mul(u_flip, vt)


def _rot_to_theta(r: tuple[tuple[float, float], tuple[float, float]]) -> float:
    return math.atan2(r[1][0], r[0][0])


def align_printable_layout_rigid_2d(
    layout: PrintableLayout,
    control_points: Sequence[ControlPoint],
    *,
    tolerance_m: float,
) -> tuple[AlignedLayout, AlignmentReport]:
    """
    Ağırlıklı 2D Kabsch / Procrustes: rijit dönüşüm (ölçek yok).

    En az 2 kontrol noktası gerekir. Tolerans dışı residual -> blocked.
    """
    tol = float(tolerance_m)
    cps = list(control_points)
    n = len(cps)
    w = _weights(cps)

    if n < 2:
        ident = RigidTransform2D(theta_rad=0.0, tx_m=0.0, ty_m=0.0)
        report = AlignmentReport(
            transform_type="rigid_2d",
            point_count=n,
            residual_mean_m=float("inf"),
            residual_max_m=float("inf"),
            tolerance_m=tol,
            blocked=True,
            transform=ident,
            reasons=("En az 2 kontrol noktası gerekir.",),
            notes=("Hizalama uygulanmadı (kimlik dönüşüm).",),
        )
        return (
            AlignedLayout(units="m", objects=layout.objects, rejected=layout.rejected),
            report,
        )

    cad_pts = [(float(cp.cad_x), float(cp.cad_y)) for cp in cps]
    site_pts = [(float(cp.site_x), float(cp.site_y)) for cp in cps]

    pcx, pcy, _sw = _centroid2(cad_pts, w)
    qcx, qcy, sw = _centroid2(site_pts, w)
    if sw <= 0.0:
        ident = RigidTransform2D(theta_rad=0.0, tx_m=0.0, ty_m=0.0)
        report = AlignmentReport(
            transform_type="rigid_2d",
            point_count=n,
            residual_mean_m=float("inf"),
            residual_max_m=float("inf"),
            tolerance_m=tol,
            blocked=True,
            transform=ident,
            reasons=("Ağırlık toplamı geçersiz.",),
            notes=("Hizalama uygulanmadı (kimlik dönüşüm).",),
        )
        return (
            AlignedLayout(units="m", objects=layout.objects, rejected=layout.rejected),
            report,
        )

    # Çapraz kovaryans: H = sum_i w_i * (site_i - q_c) * (cad_i - p_c)^T
    h00 = h01 = h10 = h11 = 0.0
    for i in range(n):
        wi = w[i]
        px = cad_pts[i][0] - pcx
        py = cad_pts[i][1] - pcy
        qx = site_pts[i][0] - qcx
        qy = site_pts[i][1] - qcy
        h00 += wi * qx * px
        h01 += wi * qx * py
        h10 += wi * qy * px
        h11 += wi * qy * py
    h = ((h00, h01), (h10, h11))

    fro = math.sqrt(h00 * h00 + h01 * h01 + h10 * h10 + h11 * h11)
    if fro < 1e-15:
        ident = RigidTransform2D(theta_rad=0.0, tx_m=0.0, ty_m=0.0)
        report = AlignmentReport(
            transform_type="rigid_2d",
            point_count=n,
            residual_mean_m=float("inf"),
            residual_max_m=float("inf"),
            tolerance_m=tol,
            blocked=True,
            transform=ident,
            reasons=("Kovaryans matrisi tekil; rijit dönüşüm güvenilir değil.",),
            notes=("Hizalama uygulanmadı (kimlik dönüşüm).",),
        )
        return (
            AlignedLayout(units="m", objects=layout.objects, rejected=layout.rejected),
            report,
        )

    r = _fix_reflection(h)
    theta = _rot_to_theta(r)
    # t = q_cent - R @ p_cent
    rpcx = r[0][0] * pcx + r[0][1] * pcy
    rpcy = r[1][0] * pcx + r[1][1] * pcy
    tx = qcx - rpcx
    ty = qcy - rpcy
    xf = RigidTransform2D(theta_rad=theta, tx_m=tx, ty_m=ty)

    residuals: list[float] = []
    for i in range(n):
        sx, sy = xf.apply_xy(cad_pts[i][0], cad_pts[i][1])
        dx = sx - site_pts[i][0]
        dy = sy - site_pts[i][1]
        residuals.append(math.hypot(dx, dy))

    mean_r = sum(residuals) / float(n)
    max_r = max(residuals)
    blocked = max_r > tol
    reasons: list[str] = []
    if blocked:
        reasons.append(
            f"Azami residual ({max_r:.6f} m) toleransı ({tol:.6f} m) aştı; execution öncesi engelleme önerilir."
        )
    notes = (
        "Model: rijit 2D (dönme + öteleme), ölçek yok.",
        f"theta_deg={math.degrees(theta):.6f}",
        f"tx_m={tx:.9f}, ty_m={ty:.9f}",
    )

    aligned_objects: list[LineObject | PolylineObject] = []
    for obj in layout.objects:
        if isinstance(obj, LineObject):
            x1, y1 = xf.apply_xy(obj.x1, obj.y1)
            x2, y2 = xf.apply_xy(obj.x2, obj.y2)
            aligned_objects.append(LineObject(x1, y1, x2, y2, obj.source, tag=obj.tag))
        else:
            pts = tuple(xf.apply_xy(px, py) for px, py in obj.points)
            aligned_objects.append(PolylineObject(pts, obj.closed, obj.source, tag=obj.tag))

    report = AlignmentReport(
        transform_type="rigid_2d",
        point_count=n,
        residual_mean_m=mean_r,
        residual_max_m=max_r,
        tolerance_m=tol,
        blocked=blocked,
        transform=xf,
        reasons=tuple(reasons),
        notes=tuple(notes),
    )
    return (
        AlignedLayout(units="m", objects=tuple(aligned_objects), rejected=layout.rejected),
        report,
    )


