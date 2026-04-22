import React, { useRef, useState } from "react";

interface Props {
  accept: string;
  label: string;
  yardim: string;
  onFile: (file: File) => void;
  yukleniyor?: boolean;
}

export function FileDropzone({ accept, label, yardim, onFile, yukleniyor }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [aktif, setAktif] = useState(false);

  return (
    <div
      className={`dropzone ${aktif ? "dropzone--aktif" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setAktif(true);
      }}
      onDragLeave={() => setAktif(false)}
      onDrop={(e) => {
        e.preventDefault();
        setAktif(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <strong>{label}</strong>
      <p>{yardim}</p>
      <span>{yukleniyor ? "Yükleniyor..." : "Dosya seç veya sürükle bırak"}</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
        hidden
      />
    </div>
  );
}
