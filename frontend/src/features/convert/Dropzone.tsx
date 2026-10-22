import clsx from "clsx";
import { FileUp, LoaderCircle } from "lucide-react";
import { type DragEvent, useId, useRef, useState } from "react";

const FORMATS = ["PDF", "CSV", "TXT", "XLSX", "XLS", "OFX", "QIF", "JSON"];
export const ACCEPT = ".pdf,.csv,.tsv,.txt,.prn,.dat,.xlsx,.xlsm,.xls,.ofx,.qfx,.qif,.json";

/** Zone de dépôt (glisser-déposer ou choix du fichier) ; un seul fichier à la fois. */
export function Dropzone({ busy, onFile, compact = false }: { busy: boolean; onFile: (file: File) => void; compact?: boolean }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const hintId = useId();

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files[0];
    if (file && !busy) onFile(file);
  };

  return (
    <div
      data-over={over}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={clsx("convert-drop flex flex-col items-center justify-center rounded-xl text-center", compact ? "gap-2 px-4 py-6" : "gap-4 px-6 py-14")}
    >
      <span className={clsx("atelier-brand__tile", !compact && "scale-125")} aria-hidden>
        {busy ? <LoaderCircle className="animate-spin" /> : <FileUp />}
      </span>
      <div>
        <p className={clsx("font-semibold", compact ? "text-sm" : "text-lg")}>{busy ? "Conversion en cours…" : "Déposez un relevé ou un fichier"}</p>
        <p id={hintId} className="mt-1 text-xs text-muted">
          Relevé bancaire en PDF, export CSV ou TXT, classeur Excel, fichier OFX ou QIF. Rien ne quitte la machine.
        </p>
      </div>
      <button type="button" disabled={busy} onClick={() => input.current?.click()} aria-describedby={hintId} className="atelier-btn-primary rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50">
        Choisir un fichier
      </button>
      {!compact && (
        <ul className="flex flex-wrap justify-center gap-1.5" aria-label="Formats acceptés">
          {FORMATS.map((f) => (
            <li key={f} className="rounded-full border border-border px-2 py-0.5 font-mono text-[11px] text-muted">
              {f}
            </li>
          ))}
        </ul>
      )}
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-label="Fichier à convertir"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onFile(file);
        }}
      />
    </div>
  );
}
