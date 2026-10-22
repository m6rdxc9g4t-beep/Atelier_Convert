"""« Envoyer dans Atelier Tab » : écriture d'une table dans le dossier de données de Tab.

Format (Atelier Tab, `src/storage/format.ts`, `atelier_tab` v1) :

    ~/Atelier_Tab/
    ├── atelier.json            espaces de travail, projets (lu ici, jamais écrit)
    └── tables/<id>.json        une table : colonnes (fields), lignes (records), vues

Tab rattache à son projet (`projectId`) une table présente dans `tables/` même si l'index ne la déclare
pas encore, et surveille le dossier : la table apparaît aussitôt dans l'app ouverte. Convert n'écrit donc
**que** le nouveau fichier de table (écriture atomique : fichier caché temporaire puis renommage), jamais
`atelier.json` ni une table existante. Aucun réseau.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any

from app.schemas.convert import CellValue, Column, ColumnType, TabProject, TabStatus

ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"

TAB_TYPES: dict[ColumnType, str] = {
    "text": "text",
    "number": "number",
    "currency": "currency",
    "date": "date",
    "boolean": "checkbox",
}


class TabError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def new_id(prefix: str) -> str:
    """Identifiant au format de Tab (`tbl_k3j9x0a1bz`)."""
    return f"{prefix}_{''.join(secrets.choice(ID_ALPHABET) for _ in range(10))}"


class TabFolder:
    """Dossier de données d'Atelier Tab."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = threading.Lock()

    def _index(self) -> dict[str, Any] | None:
        path = self.directory / "atelier.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise TabError(f"atelier.json illisible dans {self.directory} : {exc}") from exc
        return data if isinstance(data, dict) else None

    def status(self) -> TabStatus:
        """Projets d'Atelier Tab (espace › projet), ou la raison pour laquelle le dossier est introuvable."""
        directory = str(self.directory)
        try:
            index = self._index()
        except TabError as exc:
            return TabStatus(found=False, directory=directory, detail=exc.message)
        if index is None:
            return TabStatus(
                found=False,
                directory=directory,
                detail="Dossier d'Atelier Tab introuvable : ouvrez Atelier Tab une première fois (ou indiquez "
                "ATELIER_TAB_DATA_DIR).",
            )
        workspaces = index.get("workspaces") if isinstance(index.get("workspaces"), dict) else {}
        projects = index.get("projects") if isinstance(index.get("projects"), dict) else {}
        order = [w for w in index.get("workspaceOrder", []) if w in workspaces] or list(workspaces)
        listed: list[TabProject] = []
        seen: set[str] = set()
        for wid in order:
            ws = workspaces.get(wid) or {}
            for pid in ws.get("projectIds", []):
                p = projects.get(pid)
                if isinstance(p, dict) and pid not in seen:
                    seen.add(pid)
                    listed.append(_project(pid, p, str(ws.get("name") or "")))
        for pid, p in projects.items():
            if pid not in seen and isinstance(p, dict):
                ws = workspaces.get(p.get("workspaceId")) or {}
                listed.append(_project(pid, p, str(ws.get("name") or "")))
        detail = None if listed else "Aucun projet dans Atelier Tab : créez-en un, puis revenez ici."
        return TabStatus(found=True, directory=directory, projects=listed, detail=detail)

    def write_table(
        self, project_id: str, name: str, columns: list[Column], rows: list[dict[str, CellValue]]
    ) -> tuple[str, str, str]:
        """Écrit une nouvelle table dans le projet ; renvoie (id de table, nom du projet, chemin relatif)."""
        status = self.status()
        if not status.found:
            raise TabError(status.detail or "Dossier d'Atelier Tab introuvable.", 404)
        project = next((p for p in status.projects if p.id == project_id), None)
        if project is None:
            raise TabError("Projet introuvable dans Atelier Tab (supprimé ou renommé ?) : actualisez la liste.", 404)
        cols = [c for c in columns if c.include]
        if not cols:
            raise TabError("Aucune colonne à envoyer : incluez au moins une colonne.")
        table = build_table(project_id, name, cols, rows)
        tables_dir = self.directory / "tables"
        with self._lock:
            tables_dir.mkdir(parents=True, exist_ok=True)
            target = tables_dir / f"{table['id']}.json"
            while target.exists():  # collision (improbable) : nouvel identifiant
                table["id"] = new_id("tbl")
                target = tables_dir / f"{table['id']}.json"
            tmp = tables_dir / f".{target.name}.{os.getpid()}.tmp"
            tmp.write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, target)
        return str(table["id"]), project.name, f"tables/{target.name}"


def _project(pid: str, p: dict[str, Any], workspace: str) -> TabProject:
    tables = p.get("tableIds")
    return TabProject(
        id=pid,
        name=str(p.get("name") or pid),
        workspace=workspace,
        tables=len(tables) if isinstance(tables, list) else 0,
    )


def build_table(project_id: str, name: str, columns: list[Column], rows: list[dict[str, CellValue]]) -> dict[str, Any]:
    """Fichier de table au format d'Atelier Tab (champs typés, lignes, vue grille)."""
    field_ids = [new_id("fld") for _ in columns]
    title_index = next((i for i, c in enumerate(columns) if c.role == "label"), None)
    if title_index is None:
        title_index = next((i for i, c in enumerate(columns) if c.type == "text"), None)
    fields: dict[str, Any] = {}
    for i, (fid, col) in enumerate(zip(field_ids, columns, strict=True)):
        field: dict[str, Any] = {"id": fid, "label": col.label, "type": TAB_TYPES[col.type]}
        if col.type == "currency":
            field["options"] = {"currency": "EUR", "decimals": 2}
        field["atelierMapping"] = "entity_title" if i == title_index else "custom"
        if col.role == "label" or (col.type == "text" and i == title_index):
            field["width"] = 320
        fields[fid] = field
    records: dict[str, Any] = {}
    row_order: list[str] = []
    for row in rows:
        rid = new_id("rec")
        cells: dict[str, Any] = {}
        for fid, col in zip(field_ids, columns, strict=True):
            value = _tab_value(row.get(col.key), col)
            if value is not None:
                cells[fid] = value
        records[rid] = {"id": rid, "kind": "data", "cells": cells}
        row_order.append(rid)
    view_id = new_id("view")
    return {
        "id": new_id("tbl"),
        "projectId": project_id,
        "name": name,
        "fieldOrder": field_ids,
        "rowOrder": row_order,
        "fields": fields,
        "records": records,
        "views": [
            {"id": view_id, "name": "Grille", "mode": "hybrid", "filters": [], "sorts": [], "hiddenFieldIds": []}
        ],
        "activeViewId": view_id,
    }


def _tab_value(value: CellValue, col: Column) -> str | float | bool | None:
    """Valeur stockée par Tab : nombre, « AAAA-MM-JJ », booléen ou texte. Un texte commençant par « = »
    serait lu comme une formule : il est précédé d'une apostrophe."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value if col.type == "boolean" else ("oui" if value else "non")
    if isinstance(value, int | float):
        return float(value) if col.type in {"number", "currency"} else str(value)
    text = str(value)
    if text.startswith("="):
        text = "'" + text
    return text
