import React, { useRef } from "react";
import { COPY } from "../../content";

interface Props {
  aktif: boolean;
  kabulBilgisi: string;
  dosya: File | null;
  suruklemeAktif: boolean;
  yukleniyor: boolean;
  onDosyaSec: (file: File | null) => void;
  onSuruklemeDurumu: (aktifMi: boolean) => void;
}

export function PlanYukleDropzone({
  aktif,
  kabulBilgisi,
  dosya,
  suruklemeAktif,
  yukleniyor,
  onDosyaSec,
  onSuruklemeDurumu,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <section
      className={`plan-load-dropzone ${suruklemeAktif ? "plan-load-dropzone--aktif" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        if (!aktif) {
          return;
        }
        onSuruklemeDurumu(true);
      }}
      onDragLeave={() => onSuruklemeDurumu(false)}
      onDrop={(event) => {
        event.preventDefault();
        onSuruklemeDurumu(false);
        if (!aktif) {
          return;
        }
        const nextFile = event.dataTransfer.files?.[0] ?? null;
        onDosyaSec(nextFile);
      }}
    >
      <div className="plan-load-dropzone__copy">
        <p className="plan-load-dropzone__eyebrow">{COPY.ekranlar.planYukle.dropzoneBaslik}</p>
        <h3>{COPY.butonlar.dosyaSec}</h3>
        <p>{COPY.ekranlar.planYukle.dropzoneAciklama}</p>
      </div>

      <div className="plan-load-dropzone__meta">
        <div>
          <span className="plan-load-dropzone__meta-label">{COPY.ortak.kabulEdilenFormatlar}</span>
          <strong>{kabulBilgisi}</strong>
        </div>
        <div>
          <span className="plan-load-dropzone__meta-label">{COPY.ortak.yuklemeDurumu}</span>
          <strong>
            {yukleniyor
              ? COPY.durumlar.calisiyor
              : dosya
                ? COPY.ekranlar.planYukle.dosyaHazir
                : COPY.ekranlar.planYukle.dosyaBekliyor}
          </strong>
        </div>
      </div>

      <div className="plan-load-dropzone__actions">
        <button
          className="secondary-button"
          type="button"
          onClick={() => inputRef.current?.click()}
        >
          {COPY.butonlar.dosyaSec}
        </button>
        <span className="plan-load-dropzone__file-name">
          {dosya ? `${dosya.name} • ${Math.max(1, Math.round(dosya.size / 1024))} KB` : COPY.geriBildirim.bos.dosyaYok}
        </span>
      </div>

      <input
        ref={inputRef}
        hidden
        type="file"
        accept={kabulBilgisi}
        onChange={(event) => {
          const nextFile = event.target.files?.[0] ?? null;
          onDosyaSec(nextFile);
        }}
      />
    </section>
  );
}
