import React from "react";

function fmtNum(x) {
  if (x == null) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return String(x);
  return n.toFixed(6);
}

export default function AlignmentSummaryCard({ alignment }) {
  if (!alignment) {
    return (
      <div>
        <h3 className="align2-card__h">Özet</h3>
        <p className="align2-muted">Henüz rapor yok. Hizalamayı çalıştırın.</p>
      </div>
    );
  }

  const tf = alignment.transform || {};
  const blocked = alignment.blocked === true;
  const allowed = !blocked && (alignment.point_count ?? 0) >= 2;

  return (
    <div>
      <h3 className="align2-card__h">Hizalama özeti</h3>
      <ul className="align2-summary-list">
        <li>
          Dönüşüm: <strong>{alignment.transform_type ?? "—"}</strong>
        </li>
        <li>
          Nokta sayısı: <strong>{alignment.point_count ?? "—"}</strong>
        </li>
        <li>
          Ortalama residual (m): <strong>{fmtNum(alignment.residual_mean_m)}</strong>
        </li>
        <li>
          Max residual (m): <strong>{fmtNum(alignment.residual_max_m)}</strong>
        </li>
        <li>
          Tolerans (m): <strong>{fmtNum(alignment.tolerance_m)}</strong>
        </li>
        <li>
          Durum:{" "}
          <strong className={blocked ? "align2-err" : "align2-ok"}>
            {blocked ? "engelli (blocked)" : "izin verildi (allowed)"}
          </strong>
        </li>
        {tf.theta_deg != null && (
          <li>
            θ (°): <strong>{Number(tf.theta_deg).toFixed(4)}</strong> · tx:{" "}
            <strong>{Number(tf.tx_m).toFixed(4)}</strong> m · ty: <strong>{Number(tf.ty_m).toFixed(4)}</strong> m
          </li>
        )}
      </ul>
      {(alignment.reasons?.length > 0 || alignment.notes?.length > 0) && (
        <div className="align2-notes">
          {alignment.reasons?.length > 0 && (
            <div>
              <div className="align2-notes__label">Nedenler</div>
              <ul>
                {alignment.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          {alignment.notes?.length > 0 && (
            <div>
              <div className="align2-notes__label">Notlar</div>
              <ul>
                {alignment.notes.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <p className="align2-next-hint">
        {allowed
          ? "Sonraki adım: Plan’da doğrulama veya Execute ile job — hizalama kapısı açık."
          : blocked
            ? "Tolerans dışı veya geometri tekilliği: kontrol noktalarını veya toleransı güncelleyin."
            : "Yeterli kontrol noktası yok veya hizalama uygulanmadı."}
      </p>
    </div>
  );
}
