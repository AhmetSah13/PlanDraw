import React from "react";

export default function ToleranceInputCard({ toleranceM, onChange, disabled }) {
  return (
    <div className="align2-tolerance">
      <h3 className="align2-card__h">Tolerans</h3>
      <p className="align2-muted">
        İzin verilen maksimum residual (m). Aşılırsa hizalama <strong>engelli</strong> sayılır.
      </p>
      <label className="align2-field">
        <span>tolerance_m (m)</span>
        <input
          className="align2-input"
          type="number"
          min="0.0001"
          step="0.001"
          value={toleranceM}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </label>
    </div>
  );
}
