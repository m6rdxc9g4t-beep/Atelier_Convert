"""Exemples de la suite (`exemples-suite/`, format `atelier-exemples/1`).

Le dossier est généré par Atelier_Deploy (`exemples/generer.py`) et copié tel quel dans chaque app : une histoire
fictive par fichier `<histoire>.json`, et pour Convert les fichiers à convertir (relevés PDF, CSV) dans
`<histoire>/`. Les mêmes données traversent toute la suite : le relevé converti ici est celui que Tab range, que Viz
analyse et que Trésorerie compare au budget.

Lecture seule : rien n'est écrit dans ce dossier. Un fichier n'est lu que s'il est déclaré par son histoire (aucun
chemin venu de la requête n'atteint le disque).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.schemas.exemples import ExempleEtape, ExempleFichier, ExempleHistoire

FORMAT = "atelier-exemples/1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ExempleError(Exception):
    def __init__(self, message: str, status_code: int = 404) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ExemplesSuite:
    """Histoires d'exemple livrées avec l'app."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _json(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) and data.get("format") == FORMAT else None

    def histoires(self) -> list[ExempleHistoire]:
        """Histoires de l'index, avec les fichiers à convertir de chacune (dossier absent → liste vide)."""
        index = self._json(self.directory / "index.json")
        if index is None:
            return []
        out = []
        for h in index.get("histoires", []):
            part = self._part(str(h.get("id", "")))
            if part is None:
                continue
            out.append(
                ExempleHistoire(
                    id=h["id"],
                    titre=h["titre"],
                    sous_titre=h.get("sous_titre", ""),
                    secteur=h.get("secteur", ""),
                    resume=h.get("resume", ""),
                    parcours=[ExempleEtape(**e) for e in h.get("parcours", [])],
                    fichiers=[
                        ExempleFichier(index=i, titre=f["titre"], description=f.get("description", ""), type=f["type"])
                        for i, f in enumerate(part.get("fichiers", []))
                    ],
                    tab_projet=part.get("tab", {}).get("projet", ""),
                )
            )
        return out

    def _part(self, histoire: str) -> dict[str, Any] | None:
        if not ID_RE.match(histoire):
            return None
        return self._json(self.directory / f"{histoire}.json")

    def fichier(self, histoire: str, index: int) -> tuple[bytes, str, str]:
        """(contenu, nom du fichier, nom de la conversion) du fichier n° `index` de l'histoire."""
        part = self._part(histoire)
        if part is None:
            raise ExempleError("Exemple introuvable.")
        fichiers = part.get("fichiers", [])
        if not 0 <= index < len(fichiers):
            raise ExempleError("Fichier d'exemple introuvable.")
        f = fichiers[index]
        path = (self.directory / f["fichier"]).resolve()
        if self.directory.resolve() not in path.parents or not path.is_file():
            raise ExempleError("Fichier d'exemple introuvable.")
        return path.read_bytes(), path.name, f.get("nom_conversion") or f["titre"]
