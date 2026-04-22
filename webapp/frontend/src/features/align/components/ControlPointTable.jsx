import React from "react";

export default function ControlPointTable({ rows, onChange, onAdd, onRemove }) {
  return (
    <div className="align2-cp">
      <div className="align2-cp__toolbar">
        <button type="button" className="align2-btn align2-btn--ghost" onClick={onAdd}>
          Satır ekle
        </button>
      </div>
      <div className="align2-cp__scroll">
        <table className="align2-cp__table">
          <thead>
            <tr>
              <th>cad_x</th>
              <th>cad_y</th>
              <th>site_x</th>
              <th>site_y</th>
              <th>etiket</th>
              <th>ağırlık</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={idx}>
                <td>
                  <input
                    className="align2-input"
                    type="text"
                    inputMode="decimal"
                    value={row.cad_x}
                    onChange={(e) => onChange(idx, "cad_x", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="align2-input"
                    type="text"
                    inputMode="decimal"
                    value={row.cad_y}
                    onChange={(e) => onChange(idx, "cad_y", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="align2-input"
                    type="text"
                    inputMode="decimal"
                    value={row.site_x}
                    onChange={(e) => onChange(idx, "site_x", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="align2-input"
                    type="text"
                    inputMode="decimal"
                    value={row.site_y}
                    onChange={(e) => onChange(idx, "site_y", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="align2-input align2-input--sm"
                    type="text"
                    value={row.label}
                    onChange={(e) => onChange(idx, "label", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="align2-input align2-input--sm"
                    type="text"
                    inputMode="decimal"
                    value={row.weight}
                    onChange={(e) => onChange(idx, "weight", e.target.value)}
                    placeholder="1"
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="align2-btn align2-btn--ghost"
                    onClick={() => onRemove(idx)}
                    disabled={rows.length <= 2}
                    title="Satırı sil"
                  >
                    Sil
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="align2-hint">
        En az <strong>iki</strong> tam satır gerekir. CAD sütunu plan (layout) koordinatı, site sütunu saha
        ölçümüdür (metre).
      </p>
    </div>
  );
}
