import { RotateCcw, SlidersHorizontal } from "lucide-react";
import { useEffect, useId, useState } from "react";

import type { ConversionView, ParseOptions } from "../../types/convert";
import { DEFAULT_OPTIONS } from "../../types/convert";
import { Field, Panel, Segmented, inputClass } from "./panels";

const ENCODINGS = [
  { value: "", label: "Automatique" },
  { value: "utf-8", label: "UTF-8" },
  { value: "cp1252", label: "Windows-1252 (Excel français)" },
  { value: "latin-1", label: "ISO-8859-1 (Latin-1)" },
  { value: "mac_roman", label: "Mac Roman" },
];

const DELIMITERS = [
  { value: "", label: "Auto" },
  { value: ";", label: "« ; »" },
  { value: ",", label: "« , »" },
  { value: "\t", label: "Tab" },
  { value: "|", label: "« | »" },
];

/** Options de lecture : selon le type de fichier, puis mise en forme commune. « Relire » relance la conversion. */
export function OptionsPanel({ conversion, busy, onApply }: { conversion: ConversionView; busy: boolean; onApply: (o: ParseOptions) => void }) {
  const [opts, setOpts] = useState<ParseOptions>(conversion.options);
  useEffect(() => setOpts(conversion.options), [conversion.options]);
  const ids = { pages: useId(), year: useId(), enc: useId(), skip: useId(), sheet: useId() };
  const kind = conversion.source.kind;
  const set = (patch: Partial<ParseOptions>) => setOpts((o) => ({ ...o, ...patch }));
  const dirty = JSON.stringify(opts) !== JSON.stringify(conversion.options);
  const edits = Object.keys(conversion.edited).length;
  const isText = kind === "csv" || kind === "txt";
  const isSheet = kind === "xlsx" || kind === "xls";
  const tabular = isText || isSheet || kind === "pdf" || kind === "image" || kind === "json";

  return (
    <Panel title="Lecture du fichier" icon={SlidersHorizontal} defaultOpen={false}>
      <div className="space-y-3">
        {kind === "pdf" && (
          <>
            <Field label="Lire le PDF comme">
              <Segmented
                label="Lire le PDF comme"
                value={opts.pdf_mode}
                onChange={(v) => set({ pdf_mode: v })}
                options={[
                  { value: "auto", label: "Auto" },
                  { value: "statement", label: "Relevé", title: "Lignes datées avec des montants (Débit / Crédit)" },
                  { value: "tables", label: "Tableaux", title: "Tableaux détectés dans les pages" },
                  { value: "text", label: "Texte", title: "Une ligne de texte par ligne (pour l'IA)" },
                ]}
              />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Pages" htmlFor={ids.pages}>
                <input id={ids.pages} value={opts.pages ?? ""} placeholder="toutes" onChange={(e) => set({ pages: e.target.value || null })} className={inputClass} />
              </Field>
              <Field label="Année des dates" htmlFor={ids.year}>
                <input
                  id={ids.year}
                  type="number"
                  min={1900}
                  max={2200}
                  value={opts.year ?? ""}
                  placeholder="auto"
                  onChange={(e) => set({ year: e.target.value ? Number(e.target.value) : null })}
                  className={inputClass}
                />
              </Field>
            </div>
            <p className="text-[11px] text-muted">Pages : « 1-3,5 ». Année : pour les dates écrites sans année (« 15/03 ») si la période n'est pas reconnue.</p>
            <Field label="Reconnaissance de texte (OCR)" hint="Auto : seulement pour un PDF scanné (sans texte). Toujours : relit les pages comme des images.">
              <Segmented
                label="Reconnaissance de texte (OCR)"
                value={opts.ocr}
                onChange={(v) => set({ ocr: v })}
                options={[
                  { value: "auto", label: "Auto" },
                  { value: "always", label: "Toujours" },
                  { value: "never", label: "Jamais" },
                ]}
              />
            </Field>
          </>
        )}

        {kind === "image" && (
          <p className="text-[11px] text-muted">
            Image lue par OCR (Tesseract, sur la machine). Pour un meilleur résultat : document à plat, bien éclairé, photographié de face.
          </p>
        )}

        {isText && (
          <>
            <Field label="Séparateur">
              <Segmented label="Séparateur" value={opts.delimiter ?? ""} onChange={(v) => set({ delimiter: v || null })} options={DELIMITERS} />
            </Field>
            <Field label="Encodage" htmlFor={ids.enc} hint={conversion.source.encoding ? `Détecté : ${conversion.source.encoding}` : undefined}>
              <select id={ids.enc} value={opts.encoding ?? ""} onChange={(e) => set({ encoding: e.target.value || null })} className={inputClass}>
                {ENCODINGS.map((e) => (
                  <option key={e.value} value={e.value}>
                    {e.label}
                  </option>
                ))}
              </select>
            </Field>
          </>
        )}

        {isSheet && conversion.source.sheets.length > 0 && (
          <Field label="Feuille" htmlFor={ids.sheet}>
            <select id={ids.sheet} value={opts.sheet ?? conversion.source.sheets[0]} onChange={(e) => set({ sheet: e.target.value })} className={inputClass}>
              {conversion.source.sheets.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
        )}

        {(isText || isSheet) && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="En-tête">
              <Segmented
                label="Première ligne = en-tête"
                value={opts.header === null ? "auto" : opts.header ? "oui" : "non"}
                onChange={(v) => set({ header: v === "auto" ? null : v === "oui" })}
                options={[
                  { value: "auto", label: "Auto" },
                  { value: "oui", label: "Oui" },
                  { value: "non", label: "Non" },
                ]}
              />
            </Field>
            <Field label="Lignes à ignorer" htmlFor={ids.skip}>
              <input id={ids.skip} type="number" min={0} max={10000} value={opts.skip_rows} onChange={(e) => set({ skip_rows: Math.max(0, Number(e.target.value) || 0) })} className={inputClass} />
            </Field>
          </div>
        )}

        {tabular && (
          <Field label="Mise en forme" hint="« Relevé » : colonnes Date, Libellé, Débit, Crédit, Montant (et Solde) quelle que soit la banque.">
            <Segmented
              label="Mise en forme"
              value={opts.profile}
              onChange={(v) => set({ profile: v })}
              options={[
                { value: "auto", label: "Auto" },
                { value: "statement", label: "Relevé" },
                { value: "raw", label: "Telle quelle" },
              ]}
            />
          </Field>
        )}

        <div className="grid grid-cols-2 gap-2">
          <Field label="Virgule décimale">
            <Segmented
              label="Séparateur décimal"
              value={opts.decimal}
              onChange={(v) => set({ decimal: v })}
              options={[
                { value: "auto", label: "Auto" },
                { value: ",", label: "1,5" },
                { value: ".", label: "1.5" },
              ]}
            />
          </Field>
          <Field label="Dates">
            <Segmented
              label="Ordre des dates"
              value={opts.date_order}
              onChange={(v) => set({ date_order: v })}
              options={[
                { value: "auto", label: "Auto" },
                { value: "dmy", label: "J/M" },
                { value: "mdy", label: "M/J" },
              ]}
            />
          </Field>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button type="button" disabled={busy || !dirty} onClick={() => onApply(opts)} className="atelier-btn-primary flex-1 rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40">
            Relire le fichier
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setOpts(DEFAULT_OPTIONS)}
            title="Revenir à la détection automatique"
            aria-label="Revenir à la détection automatique"
            className="rounded-md border border-border p-2 text-muted hover:bg-surface-2 hover:text-fg disabled:opacity-40"
          >
            <RotateCcw className="size-3.5" aria-hidden />
          </button>
        </div>
        {dirty && (
          <p className="text-[11px] text-muted">
            La relecture recalcule les colonnes : vos renommages et types sont remis à zéro
            {edits > 0 && <span className="text-warning">, et vos {edits} correction(s) de cellules perdues</span>}.
          </p>
        )}
      </div>
    </Panel>
  );
}
