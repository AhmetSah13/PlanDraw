import { useRef, useState } from "react";
import { tr } from "../content/tr";

interface PlanUploadCardProps {
  fileName: string | null;
  loading: boolean;
  onFileSelect: (file: File) => void;
  onPrepare: () => void;
}

export function PlanUploadCard({
  fileName,
  loading,
  onFileSelect,
  onPrepare,
}: PlanUploadCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  function pickFile(file: File | undefined) {
    if (!file) return;
    onFileSelect(file);
  }

  return (
    <section className="panel">
      <h2 className="text-lg font-semibold text-slate-900">{tr.upload.title}</h2>
      <p className="mt-1 text-sm text-slate-600">{tr.upload.hint}</p>

      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          pickFile(e.dataTransfer.files[0]);
        }}
        className={`mt-4 cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragOver
            ? "border-brand-light bg-sky-50"
            : "border-slate-200 bg-slate-50/80 hover:border-brand/40"
        }`}
      >
        <p className="text-sm font-medium text-slate-700">{tr.upload.drop}</p>
        <p className="mt-2 text-xs text-slate-500">{tr.upload.formats}</p>
        <p className="mt-3 text-sm text-brand-dark">
          {fileName ?? tr.upload.noFile}
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".dxf,.json,application/json"
        className="hidden"
        onChange={(e) => pickFile(e.target.files?.[0])}
      />

      <button
        type="button"
        className="btn-primary mt-4 w-full"
        disabled={!fileName || loading}
        onClick={onPrepare}
      >
        {loading ? tr.robot.busy : tr.upload.prepare}
      </button>
    </section>
  );
}
