import React from "react";
import { Link } from "react-router-dom";

/**
 * Bir sonraki ekrana yönlendirme — birincil, isteğe bağlı ikincil ve üçüncül bağlantı.
 */
export default function NextStepCta({ primary, secondary, tertiary }) {
  return (
    <div className="oc-cta-row">
      {primary ? (
        <Link className="oc-cta oc-cta--primary" to={primary.to}>
          <span className="oc-cta__label">{primary.label}</span>
          {primary.hint ? <span className="oc-cta__hint">{primary.hint}</span> : null}
        </Link>
      ) : null}
      {secondary ? (
        <Link className="oc-cta oc-cta--secondary" to={secondary.to}>
          <span className="oc-cta__label">{secondary.label}</span>
          {secondary.hint ? <span className="oc-cta__hint">{secondary.hint}</span> : null}
        </Link>
      ) : null}
      {tertiary ? (
        <Link className="oc-cta oc-cta--tertiary" to={tertiary.to}>
          <span className="oc-cta__label">{tertiary.label}</span>
          {tertiary.hint ? <span className="oc-cta__hint">{tertiary.hint}</span> : null}
        </Link>
      ) : null}
    </div>
  );
}
