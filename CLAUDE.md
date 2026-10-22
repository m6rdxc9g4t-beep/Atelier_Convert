# CLAUDE.md — Atelier Convert

Instructions permanentes pour Claude lorsqu'il travaille sur ce dépôt.

## Rôle
Atelier Convert transforme des fichiers (relevés bancaires PDF, CSV, TXT, XLSX/XLS, OFX/QFX, QIF, JSON) en **tables
typées** pour **Atelier Tab** : export (CSV français, CSV, TXT, XLSX, `atelier-table/1`) ou envoi direct dans un projet de
Tab. Même architecture et même design qu'Atelier Viz (FastAPI + React), dont il reprend l'infrastructure.

## Principe n°1 : local d'abord
- Hors ligne par défaut : **rien ne quitte la machine** (fichiers, conversions, exports, envoi vers Tab).
- API locale seulement : `LocalOnlyMiddleware` (`app/core/local_only.py`, docs/SUITE.md §5.1). Ne jamais l'affaiblir ; en test,
  `conftest` ajoute `testserver` à `allowed_hosts`.
- Seule « Structurer avec l'IA » peut envoyer du texte, sur demande : Ollama (local) ou Claude (mode « En ligne » seulement,
  403 sinon). L'interface dit exactement ce qui part (ligne bouclier de `EnginePicker`).
- Aucune ressource externe au chargement du frontend (pas de CDN, pas de Google Fonts).

## Stack
| Couche | Choix |
|---|---|
| Frontend | React 19 + TypeScript strict + Vite (5176), Tailwind v4, lucide-react |
| Backend | FastAPI (8010), Pydantic v2, pydantic-settings, httpx |
| Lecture | pdfplumber (mots + positions), pandas + openpyxl / xlrd, charset-normalizer, csv ; OCR : Tesseract (binaire du système) + pypdfium2 + Pillow |
| Stockage | `backend/data/conversions/<id>.json` + `backend/data/sources/<id>.<ext>` (écritures atomiques) |
| IA | `AIService` → Ollama / Claude (`ClaudeCliProvider` via `claude -p`, ou `AnthropicProvider`) — copie de Viz |

## Moteur de conversion (`app/services/convert/`)
- `values.py` : nombres FR/EN (`parse_number`), dates (`parse_date`, années à 2 chiffres, mois en lettres, OFX), types
  (`infer_type`, ≥ 90 % des valeurs), `coerce` (une valeur non convertible reste du **texte** : rien n'est perdu).
- `statement.py` : relevés. `group_lines` / `merge_numbers` (« 1 » « 234,56 » → « 1 234,56 »), `header_anchors`
  (Débit / Crédit / Montant / Solde), sinon `cluster_positions` ; `extract_statement` (opérations, libellés multi-lignes,
  soldes, années) ; `normalize` (CSV/XLSX/tableaux → colonnes normalisées) ; `summarize` (contrôle des soldes).
  Fonctions sur `Word` / `Line` : **testables sans PDF** (tests/test_pipeline.py).
- Colonnes normalisées, dans cet ordre et avec ces clés : `date`, `date_de_valeur`, `libelle`, `debit`, `credit`
  (positifs), `montant` (signé), `solde`, puis les autres colonnes. Ne pas les renommer : tests, Tab et exports en dépendent.
- `pipeline.py` : `convert(data, filename, options)` choisit le lecteur (`detect_kind` : contenu puis extension) et applique
  `profile` (auto / statement / raw). Tout nouveau format : lecteur + extension dans `EXTENSIONS` + test + `ACCEPT` du front.
- `ocr.py` : Tesseract lancé **sans shell**, image sur l'entrée standard, TSV sur la sortie (`-c tessedit_create_tsv=1`,
  `--psm 6`), délai borné ; mots convertis en `Word` en points (PDF : `dpi/72` ; image : largeur A4) pour que `statement.py`
  les lise comme un PDF texte. `fix_token` ne corrige que des jetons en forme de montant ou de date (jamais un libellé).
  Exécutable cherché hors PATH (Finder) ; jamais un chemin relatif. `pipeline._needs_ocr` : auto = moins de 20 caractères
  par page. Une ligne datée au montant illisible (`Txn.garbled`) est gardée sans montant et signalée. Tests : moteur simulé
  (`runner`), tests réels ignorés sans Tesseract ; `conftest` coupe l'OCR (`convert_ocr_enabled=False`).
- `writers.py` : CSV français = `;`, virgule décimale, `JJ/MM/AAAA`, UTF-8 **avec BOM** (Excel FR) ; seules les colonnes
  incluses sont écrites.
- `tab.py` : **écrit un seul fichier** `tables/<tbl_id>.json` dans le dossier de Tab (format `atelier_tab` v1,
  `src/storage/format.ts` de Tab), jamais `atelier.json` ni une table existante ; écriture atomique (fichier caché `.…tmp`,
  ignoré par la surveillance de Tab). Toute évolution du format de Tab se reporte ici avec un test
  (`test_send_to_tab_validates_with_tab_schema`).
- `ai_structure.py` : prompt système = consignes seulement ; le texte du document voyage dans la conversation dans
  `<donnees>…</donnees>` (docs/SUITE.md §5.3–5.4) ; borné par `AI_MAX_LINES` / `AI_MAX_CHARS`.

## Nœud Atelier (docs/SUITE.md §7)
- Manifeste `app/services/atelier/manifest.py` (`app: "convert"`) ; schémas `app/schemas/atelier.py`.
- **Tout nouvel événement** se déclare dans `EVENT_TYPES` et s'émet par `EventJournal.emit` depuis `ConversionService`
  (jamais depuis une route). `data` : identifiants, libellés, formats, nombres — jamais de ligne, de chemin ni de texte du fichier.
- `conversions.convert_file` reçoit le fichier **en base64**, jamais un chemin (le nœud ne lit pas le disque à la demande).
- Écritures qui créent : `Idempotency-Key` (`_idempotent` dans `routes/atelier.py`).

## Application de bureau
Reprise d'Atelier Viz (voir son CLAUDE.md) : `backend/desktop.py` → `app/desktop.py` (pywebview + uvicorn, port 8010),
`app/launcher.py` (mise à jour automatique après `git pull`, docs/SUITE.md §8), `app/suite_apps.py` (ouvrir une autre app,
environnement minimal), `scripts/macos/build_app.sh` (`fr.atelier-convert.app`), `scripts/windows/install.ps1`
(UTF-8 avec BOM, CRLF ; `HKCU\Software\Atelier\Apps\convert`). `/api/health` renvoie `app: "atelier-convert"` : l'app de
bureau ne réutilise qu'un serveur Convert. Tout nouveau réglage de `Settings` : préfixe gardé (`CONVERT_`, `ATELIER_TAB_`,
`AI_`, `OLLAMA_`, `CLAUDE_`, `ANTHROPIC_`) ou `FOREIGN_ENV` (test_launcher). Front : fichiers par `saveFile`, liens par
`openExternal` (`lib/desktop.ts`), jamais `a.download` / `window.open` directs.

## Suite Atelier et design
- Contrat commun : `docs/SUITE.md` (Convert : §4.4 et les lignes « Convert » ; à reporter dans les autres dépôts).
- `frontend/src/styles/atelier-ds/` et `styles/atelier-brand/` : copies **verbatim** (jamais modifiées ici).
  La signature de Convert (`#C9951D`, `data-atelier-app="convert"`) est déclarée dans `index.css` (la marque source ne la
  connaît pas encore) avec `:root[data-atelier-app="convert"]` pour l'emporter sur le `:root` neutre de la marque.
- Classes de la charte : `atelier-card`, `atelier-pop`, `atelier-btn-primary`, `atelier-nav-active`, `atelier-title` ;
  texte en couleur : `text-accent-ink` ; fonds `bg-accent-soft` / `bg-accent-faint` ; champs `bg-field`.
- Logo et icônes : `scripts/brand/make_logo.py` (Chromium via Playwright) → `frontend/src/assets`, `frontend/public`,
  `scripts/macos/icon.png`, `scripts/windows/atelier-convert.ico`, `docs/brand/`.

## Règles de code
1. Routes minces, logique dans `services/` ; schémas Pydantic avec miroir TypeScript (`frontend/src/types/convert.ts`).
2. TypeScript `strict` + `noUncheckedIndexedAccess`, pas de `any` ; docstrings / JSDoc en français.
3. Code bloquant (PDF, pandas, disque) : `asyncio.to_thread`.
4. Tests : chaque route a un test pytest, chaque lecteur un fichier de test (`tests/fixtures/`, `samples/` — régénérés par
   `scripts/samples/make_samples.py`, données fictives) ; la logique front a des tests Vitest. Les tests forcent
   `claude_mode="api"` sans clé et un dossier d'Atelier Tab temporaire.

## Commandes
```bash
cd backend && source .venv/bin/activate && pytest && ruff check . && ruff format --check .
uvicorn main:app --reload --port 8010
cd frontend && npm test && npm run build && npm run dev
```

## Façon de travailler
- Avant une fonctionnalité : plan court, puis code ; après : pytest, ruff, npm test, npm run build, puis vérification
  visuelle (clair + sombre).
