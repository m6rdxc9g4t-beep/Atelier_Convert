import { ArrowLeft, FileUp, Info, LoaderCircle, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { toast } from "../../components/Toaster";
import { api } from "../../lib/api";
import { KIND_LABELS, formatSize } from "../../lib/format";
import { conversionPath, navigate } from "../../lib/router";
import type { AppInfo, CellEdit, CellValue, Column, ConversionView, ParseOptions } from "../../types/convert";
import { AiPanel } from "./AiPanel";
import { ACCEPT } from "./Dropzone";
import { ExportPanel } from "./ExportPanel";
import { OptionsPanel } from "./OptionsPanel";
import { PreviewTable } from "./PreviewTable";
import { StatementCard } from "./StatementCard";
import { TabPanel } from "./TabPanel";

const DELIMITER_LABELS: Record<string, string> = { ";": "« ; »", ",": "« , »", "\t": "tabulation", "|": "« | »", " ": "espaces" };

/** Atelier d'une conversion : aperçu modifiable, synthèse du relevé, lecture, exports, envoi vers Tab, IA. */
export function Workbench({ id, info }: { id: string; info: AppInfo | null }) {
  const [conv, setConv] = useState<ConversionView | null>(null);
  const [rows, setRows] = useState<Record<string, CellValue>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const show = useCallback((c: ConversionView) => {
    setConv(c);
    setRows(c.preview);
    setName(c.name);
  }, []);

  useEffect(() => {
    setConv(null);
    setError(null);
    api.conversions.get(id).then(show, (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [id, show]);

  const act = async (work: () => Promise<ConversionView>) => {
    setBusy(true);
    try {
      show(await work());
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const saveColumns = (columns: Column[]) => {
    if (!conv) return;
    setConv({ ...conv, table_columns: columns }); // affichage immédiat, puis valeur confirmée par le serveur
    void act(() => api.conversions.setColumns(conv.id, columns)).then(() => undefined);
  };

  /** Corrections de cellules : la conversion (synthèse, marques) et les lignes déjà chargées sont mises à jour. */
  const editCells = async (edits: CellEdit[]): Promise<boolean> => {
    if (!conv) return false;
    try {
      const result = await api.conversions.editCells(conv.id, edits);
      setConv(result.conversion);
      setRows((current) => {
        const next = [...current];
        for (const { index, values } of result.rows) if (index < next.length) next[index] = values;
        return next;
      });
      return true;
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      return false;
    }
  };

  const reparse = (options: ParseOptions) => {
    if (!conv) return;
    void act(() => api.conversions.reparse(conv.id, options));
  };

  const rename = () => {
    if (!conv || !name.trim() || name.trim() === conv.name) return setName(conv?.name ?? "");
    void act(() => api.conversions.rename(conv.id, name.trim()));
  };

  const more = async () => {
    if (!conv) return;
    try {
      const page = await api.conversions.rows(conv.id, rows.length, 500);
      setRows((r) => [...r, ...page.rows]);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  };

  const newFile = async (file: File) => {
    setBusy(true);
    try {
      const c = await api.conversions.upload(file);
      navigate(conversionPath(c.id));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <div className="mx-auto max-w-xl p-8 text-center">
        <p role="alert" className="at-alert px-3 py-2.5 text-sm">
          {error}
        </p>
        <button type="button" onClick={() => navigate("/")} className="at-btn mt-4">
          Revenir à l'accueil
        </button>
      </div>
    );
  }
  if (!conv)
    return (
      <p className="flex items-center justify-center gap-2 p-8 text-sm text-muted" role="status">
        <LoaderCircle className="size-4 animate-spin" aria-hidden /> Chargement de la conversion…
      </p>
    );

  const src = conv.source;
  const facts = [
    KIND_LABELS[src.kind] ?? src.kind,
    formatSize(src.size),
    src.pages ? `${src.pages} page(s)` : null,
    src.encoding ? `encodage ${src.encoding}` : null,
    src.delimiter ? `séparateur ${DELIMITER_LABELS[src.delimiter] ?? src.delimiter}` : null,
    src.ocr ? `OCR ${src.ocr_languages ?? ""}${src.ocr_confidence !== null ? ` · confiance ${Math.round(src.ocr_confidence)} %` : ""}` : null,
  ].filter(Boolean);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3 lg:gap-4 lg:px-5 lg:py-4">
      <div className="flex flex-wrap items-start gap-3">
        <button type="button" onClick={() => navigate("/")} aria-label="Accueil" title="Accueil" className="at-btn at-btn--ghost at-btn--icon">
          <ArrowLeft className="size-4" aria-hidden />
        </button>
        <div className="min-w-0 flex-1">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={rename}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            aria-label="Nom de la conversion"
            maxLength={200}
            className="h-[30px] w-full max-w-xl rounded-md border border-transparent bg-transparent px-1.5 text-lg font-semibold hover:border-border"
          />
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 px-1.5 text-xs text-muted tabular-nums">
            <span className="flex h-5 items-center rounded-sm bg-accent-soft px-1.5 font-medium whitespace-nowrap text-accent-ink">{conv.detected}</span>
            <span className="max-w-full truncate" title={src.filename}>
              {src.filename}
            </span>
            <span>· {facts.join(" · ")}</span>
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
          aria-label="Autre fichier"
          title="Convertir un autre fichier"
          className="at-btn max-sm:w-[30px] max-sm:px-0"
        >
          <FileUp className="size-3.5" aria-hidden />
          <span className="max-sm:sr-only">Autre fichier</span>
        </button>
        <input
          ref={fileInput}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-label="Autre fichier à convertir"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) void newFile(f);
          }}
        />
      </div>

      {conv.warnings.length > 0 && (
        <ul className="at-alert at-alert--warn space-y-1 px-3 py-2 text-xs" aria-label="Avertissements">
          {conv.warnings.map((w) => (
            <li key={w} className="flex items-start gap-1.5">
              {w.startsWith("Table proposée") ? <Info className="mt-px size-3.5 shrink-0" aria-hidden /> : <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />}
              {w}
            </li>
          ))}
        </ul>
      )}

      {conv.statement && <StatementCard statement={conv.statement} />}

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:gap-4 xl:flex-row">
        <div className="flex min-h-[24rem] min-w-0 flex-1 flex-col">
          <PreviewTable
            columns={conv.table_columns}
            rows={rows}
            total={conv.rows}
            busy={busy}
            edited={conv.edited}
            onColumns={saveColumns}
            onCells={editCells}
            onMore={rows.length < conv.rows ? () => void more() : null}
          />
        </div>
        <aside className="w-full shrink-0 space-y-2 overflow-y-auto xl:w-72" aria-label="Actions">
          <TabPanel conversion={conv} onSent={() => void api.conversions.get(conv.id).then(show)} />
          <ExportPanel conversionId={conv.id} />
          <OptionsPanel conversion={conv} busy={busy} onApply={reparse} />
          {conv.has_text && <AiPanel conversion={conv} info={info} onDone={show} />}
        </aside>
      </div>
    </div>
  );
}
