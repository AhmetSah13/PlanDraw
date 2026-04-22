import React from "react";
import { Link } from "react-router-dom";
import NextStepCta from "../flow/NextStepCta.jsx";
import StageStatusBadge from "../flow/StageStatusBadge.jsx";

function fmtNum(x) {
  if (x == null) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return String(x);
  return n.toFixed(6);
}

function formatWhen(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("tr-TR");
  } catch {
    return String(iso);
  }
}

/**
 * Plan sağ sütun: hizalama özeti + CTA
 */
export function PlanAlignmentCard({ align }) {
  const a = align?.alignment;
  const gate = align?.gate ?? "none";

  if (gate === "none") {
    return (
      <div className="oc-align-card oc-align-card--missing">
        <h2 className="oc-align-card__h">Hizalama (Align)</h2>
        <p className="oc-align-card__muted">
          Henüz rijit 2D hizalama çalıştırılmadı. Saha koordinatına oturtma yapılmadan çizim riski yüksek
          olabilir.
        </p>
        <NextStepCta
          primary={{ to: "/align", label: "Align ekranına git", hint: "Kontrol noktaları ve tolerans" }}
        />
      </div>
    );
  }

  if (gate === "blocked") {
    return (
      <div className="oc-align-card oc-align-card--blocked">
        <h2 className="oc-align-card__h">Hizalama (Align)</h2>
        <div className="oc-align-bridge__row">
          <StageStatusBadge status="blocked" title="Tolerans dışı veya engel" />
          <span className="oc-align-bridge__msg">Hizalama tolerans dışı — Execute öncesi düzeltin.</span>
        </div>
        <ul className="oc-align-bridge__list">
          <li>
            Son çalıştırma: <strong>{formatWhen(align.updatedAt)}</strong>
          </li>
          <li>
            Dönüşüm: <strong>{a?.transform_type ?? "—"}</strong> · nokta:{" "}
            <strong>{a?.point_count ?? "—"}</strong>
          </li>
          <li>
            residual ort / max (m): <strong>{fmtNum(a?.residual_mean_m)}</strong> /{" "}
            <strong>{fmtNum(a?.residual_max_m)}</strong>
          </li>
          <li>
            Tolerans (m): <strong>{fmtNum(a?.tolerance_m)}</strong>
          </li>
        </ul>
        {(a?.reasons?.length > 0 || a?.notes?.length > 0) && (
          <div className="oc-align-bridge__notes">
            {a?.reasons?.length > 0 && (
              <div>
                <div className="oc-align-bridge__sub">Nedenler</div>
                <ul>
                  {a.reasons.slice(0, 4).map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
            {a?.notes?.length > 0 && (
              <div>
                <div className="oc-align-bridge__sub">Notlar</div>
                <ul>
                  {a.notes.slice(0, 3).map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        <NextStepCta
          primary={{ to: "/align", label: "Align’da düzelt", hint: "Kontrol noktası veya tolerans" }}
        />
      </div>
    );
  }

  return (
    <div className="oc-align-card oc-align-card--ok">
      <h2 className="oc-align-card__h">Hizalama (Align)</h2>
      <div className="oc-align-bridge__row">
        <StageStatusBadge status="ready" title="İzin verildi" />
        <span className="oc-align-bridge__msg">Execution’a geçmeye uygun (son hizalama izin verildi).</span>
      </div>
      <ul className="oc-align-bridge__list">
        <li>
          Son çalıştırma: <strong>{formatWhen(align.updatedAt)}</strong>
        </li>
        <li>
          Dönüşüm: <strong>{a?.transform_type ?? "—"}</strong> · nokta: <strong>{a?.point_count ?? "—"}</strong>
        </li>
        <li>
          residual ort / max (m): <strong>{fmtNum(a?.residual_mean_m)}</strong> /{" "}
          <strong>{fmtNum(a?.residual_max_m)}</strong>
        </li>
        <li>
          Tolerans (m): <strong>{fmtNum(a?.tolerance_m)}</strong>
        </li>
      </ul>
      <p className="oc-align-card__muted">
        Operasyonel risk yine de sizde; analiz ve saha koşullarını göz önünde bulundurun.
      </p>
      <NextStepCta
        secondary={{ to: "/align", label: "Align’ı yeniden aç", hint: "Ölçüm güncellenirse" }}
      />
    </div>
  );
}

/**
 * Execute: gate + özet (job davranışını değiştirmez)
 */
export function ExecuteAlignmentCard({ align }) {
  const a = align?.alignment;
  const gate = align?.gate ?? "none";

  if (gate === "none") {
    return (
      <div className="oc-align-card oc-align-card--missing">
        <h2 className="oc-align-card__h">Hizalama durumu</h2>
        <p className="oc-align-card__muted">
          <strong>Uyarı:</strong> Align’da henüz hizalama yok. Job teknik olarak başlatılabilir; saha ile CAD
          eşlemesi doğrulanmamış sayılır (dry-run / simülasyon yine backend kurallarına tabidir).
        </p>
        <NextStepCta
          primary={{ to: "/align", label: "Align ekranına git", hint: "Önerilen güvenli adım" }}
        />
      </div>
    );
  }

  if (gate === "blocked") {
    return (
      <div className="oc-align-card oc-align-card--blocked">
        <h2 className="oc-align-card__h">Hizalama durumu</h2>
        <div className="oc-align-bridge__row">
          <StageStatusBadge status="blocked" title="Engelli" />
          <span className="oc-align-bridge__msg">Son hizalama tolerans dışı (blocked).</span>
        </div>
        <p className="oc-align-card__muted">
          Önerilen güvenli durum: Align’da kontrol noktalarını veya toleransı güncelleyin. Job başlatma teknik
          olarak mümkün olabilir; operasyonel olarak önerilmez.
        </p>
        <ul className="oc-align-bridge__list oc-align-bridge__list--compact">
          <li>
            Zaman: <strong>{formatWhen(align.updatedAt)}</strong>
          </li>
          <li>
            residual max / tol: <strong>{fmtNum(a?.residual_max_m)}</strong> /{" "}
            <strong>{fmtNum(a?.tolerance_m)}</strong>
          </li>
        </ul>
        {a?.reasons?.[0] && (
          <p className="oc-align-card__muted">
            <strong>Neden:</strong> {a.reasons[0]}
          </p>
        )}
        <NextStepCta
          primary={{ to: "/align", label: "Align’da düzelt", hint: "Gate’i temizlemek için" }}
        />
      </div>
    );
  }

  return (
    <div className="oc-align-card oc-align-card--ok">
      <h2 className="oc-align-card__h">Hizalama durumu</h2>
      <div className="oc-align-bridge__row">
        <StageStatusBadge status="ready" title="İzin verildi" />
        <span className="oc-align-bridge__msg">Son hizalama raporu izin veriyor (allowed).</span>
      </div>
      <ul className="oc-align-bridge__list oc-align-bridge__list--compact">
        <li>
          Zaman: <strong>{formatWhen(align.updatedAt)}</strong>
        </li>
        <li>
          residual ort / max: <strong>{fmtNum(a?.residual_mean_m)}</strong> /{" "}
          <strong>{fmtNum(a?.residual_max_m)}</strong> m
        </li>
        <li>
          Tolerans: <strong>{fmtNum(a?.tolerance_m)}</strong> m
        </li>
      </ul>
      <p className="oc-align-card__muted">
        Job başlatma için önerilen güvenli durum: uygun. Yine de analiz ve saha koşullarını kontrol edin.
      </p>
      <Link className="oc-align-link" to="/align">
        Align özeti
      </Link>
    </div>
  );
}
