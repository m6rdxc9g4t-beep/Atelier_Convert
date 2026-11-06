import { useId, useRef } from "react";
import { ArrowLeftRight, X } from "lucide-react";

/**
 * Marque commune de la Suite Atelier (styles/atelier-brand, docs/SUITE.md §1.6) : icône carrée en dégradé de la
 * signature (glyphe Lucide `arrow-left-right`) + « Atelier Convert » ; un clic ouvre la fenêtre « À propos ».
 */
export function AtelierBrand({ showName = true, nameClassName = "" }: { showName?: boolean; nameClassName?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  return (
    <>
      <button
        type="button"
        className="atelier-brand"
        aria-haspopup="dialog"
        aria-label={showName ? undefined : "À propos d'Atelier Convert"}
        title="À propos d'Atelier Convert"
        onClick={() => dialog.current?.showModal()}
      >
        <span className="atelier-brand__tile" aria-hidden="true">
          <ArrowLeftRight />
        </span>
        {showName && (
          <span className={`atelier-brand__name ${nameClassName}`}>
            <span className="atelier-brand__prefix">Atelier </span>Convert
          </span>
        )}
      </button>

      <dialog
        ref={dialog}
        className="atelier-about"
        aria-labelledby={titleId}
        onClick={(e) => {
          if (e.target === e.currentTarget) e.currentTarget.close();
        }}
      >
        <div className="atelier-about__panel">
          <button type="button" className="atelier-about__close" aria-label="Fermer" onClick={() => dialog.current?.close()}>
            <X className="size-4" aria-hidden />
          </button>
          <span className="atelier-about__icon atelier-brand__tile" aria-hidden="true">
            <ArrowLeftRight />
          </span>
          <h2 id={titleId} className="atelier-about__name">
            <span className="atelier-brand__prefix">Atelier </span>Convert
          </h2>
          <p className="atelier-about__tagline">Relevés bancaires en PDF, exports CSV, TXT, Excel, OFX ou QIF convertis en tables propres pour Atelier Tab, sans que rien ne quitte la machine.</p>
          <p className="atelier-about__suite">Suite Atelier · 100 % local</p>
        </div>
      </dialog>
    </>
  );
}
