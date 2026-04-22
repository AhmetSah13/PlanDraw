import React from "react";

/**
 * Boş durum: başlık + açıklama + opsiyonel aksiyon alanı (Link’ler vb.)
 */
export default function EmptyStatePanel({ title, children, actions }) {
  return (
    <div className="oc-empty">
      <h1 className="oc-empty__title">{title}</h1>
      <div className="oc-empty__body">{children}</div>
      {actions ? <div className="oc-empty__actions">{actions}</div> : null}
    </div>
  );
}
