import clsx from "clsx";
import { FileUp, LoaderCircle } from "lucide-react";
import { type DragEvent, useId, useRef, useState } from "react";

const FORMATS = ["PDF", "CSV", "TXT", "XLSX", "XLS", "OFX", "QIF", "JSON", "JPG", "PNG", "TIFF"];
export const ACCEPT = ".pdf,.csv,.tsv,.txt,.prn,.dat,.xlsx,.xlsm,.xls,.ofx,.qfx,.qif,.json,.png,.jpg,.jpeg,.tif,.tiff,.webp,.bmp";

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
      className={clsx("convert-drop flex flex-col items-center justify-center rounded-lg text-center", compact ? "gap-2 px-4 py-6" : "gap-3.5 px-6 py-12")}
    >
      <span className="grid size-10 place-items-center rounded-lg border border-line bg-surface-2 text-muted" aria-hidden>
        {busy ? <LoaderCircle className="size-5 animate-spin" /> : <FileUp className="size-5" />}
      </span>
      <div>
        <p className={clsx("font-semibold", compact ? "text-sm" : "text-base")}>{busy ? "Conversion en cours…" : "Déposez un relevé ou un fichier"}</p>
        <p id={hintId} className="mx-auto mt-1 max-w-lg text-sm text-muted">
          {busy
            ? "Un document scanné est lu par OCR : quelques secondes par page."
            : "Relevé bancaire en PDF (même scanné), photo, export CSV ou TXT, classeur Excel, fichier OFX ou QIF. Rien ne quitte la machine."}
        </p>
      </div>
      <button type="button" disabled={busy} onClick={() => input.current?.click()} aria-describedby={hintId} className="at-btn atelier-btn-primary">
        Choisir un fichier
      </button>
      {!compact && (
        <ul className="flex max-w-md flex-wrap justify-center gap-1" aria-label="Formats acceptés">
          {FORMATS.map((f) => (
            <li key={f} className="at-tag">
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
