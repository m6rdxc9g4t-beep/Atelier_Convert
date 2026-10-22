import { useId, useRef } from "react";
import { ArrowRightLeft } from "lucide-react";

import logo from "../../assets/logo-atelier-convert.webp";

/**
 * Marque commune de la Suite Atelier (styles/atelier-brand, docs/SUITE.md §1.6) :
 * tuile + « atelier_Convert » ; un clic ouvre la fenêtre « À propos » avec le logo en grand.
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
          <ArrowRightLeft />
        </span>
        {showName && (
          <span className={`atelier-brand__name ${nameClassName}`}>
            <span className="atelier-brand__prefix">atelier_</span>Convert
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
            ×
          </button>
          <img className="atelier-about__logo" src={logo} alt="Logo Atelier Convert" width={576} height={576} />
          <h2 id={titleId} className="atelier-about__name">
            <span className="atelier-brand__prefix">atelier_</span>Convert
          </h2>
          <p className="atelier-about__tagline">Relevés bancaires en PDF, exports CSV, TXT, Excel, OFX ou QIF convertis en tables propres pour Atelier Tab, sans que rien ne quitte la machine.</p>
          <p className="atelier-about__suite">Suite Atelier · 100 % local</p>
        </div>
      </dialog>
    </>
  );
}
